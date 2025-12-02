import { useCallback, useMemo, useState } from 'react';
import type { Mall } from '../types/store';
import type { CompetitionStats } from './useCompetition';

export type ChatMessage = { id: string; role: 'user' | 'assistant'; content: string; relatedData?: Mall[] };
export type ReportOption = { id: string; title: string; reason?: string };

type ContextSnapshot = { malls: Mall[]; stats?: CompetitionStats };
type Session = {
  id: string;
  name: string;
  createdAt: number;
  messages: ChatMessage[];
  lastQuestion?: string;
};

const INITIAL_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content: '您好，我是智能业务助手。可以直接问我「深圳有哪些缺口机会？」或「帮我列个商场进入优先级建议」，我会结合当前筛选的商场数据给出建议。',
};

const mapStatusLabel = (mall: Mall): string => {
  switch (mall.status) {
    case 'gap':
      return '缺口机会';
    case 'blocked':
      return '排他';
    case 'captured':
      return '已进驻';
    case 'opportunity':
      return '高潜';
    case 'blue_ocean':
      return '蓝海';
    default:
      return '中性';
  }
};

const pickTopMalls = (malls: Mall[]): Mall[] => {
  const candidates = malls.filter((m) => {
    const isGap = m.status === 'gap' && !m.instaOpened;
    const isTarget = m.djiTarget && !m.instaOpened;
    return isGap || isTarget;
  });
  const sorted = [...candidates].sort((a, b) => {
    const score = (mall: Mall) => {
      if (mall.status === 'gap') return 0;
      if (mall.djiTarget) return 1;
      return 2;
    };
    const sA = score(a);
    const sB = score(b);
    if (sA !== sB) return sA - sB;
    const cityCmp = (a.city || '').localeCompare(b.city || '', 'zh-CN');
    if (cityCmp !== 0) return cityCmp;
    return (a.mallName || '').localeCompare(b.mallName || '', 'zh-CN');
  });
  const picked = sorted.slice(0, 20);
  return picked.length ? picked : malls.slice(0, 10);
};

const normalizeRegion = (name?: string | null) => (name || '').replace(
  /(省|市|自治区|壮族自治区|回族自治区|维吾尔自治区|地区|自治州|州|盟|区|县)$/u,
  '',
);

const inferBrandFromQuestion = (question: string): 'DJI' | 'Insta360' | 'all' => {
  const lower = question.toLowerCase();
  if (lower.includes('dji') || question.includes('大疆')) return 'DJI';
  if (lower.includes('insta') || lower.includes('影石') || question.includes('影石')) return 'Insta360';
  return 'all';
};

const pickOpenedMalls = (malls: Mall[], brand: 'DJI' | 'Insta360' | 'all' = 'all'): Mall[] => {
  const opened = malls.filter((m) => {
    if (brand === 'DJI') return m.djiOpened;
    if (brand === 'Insta360') return m.instaOpened;
    return m.djiOpened || m.instaOpened;
  });
  return opened
    .sort(
      (a, b) =>
        (a.city || '').localeCompare(b.city || '', 'zh-CN') ||
        (a.mallName || '').localeCompare(b.mallName || '', 'zh-CN'),
    )
    .slice(0, 20);
};

const buildDataSnapshot = (stats?: CompetitionStats) => {
  if (!stats) return '暂无统计数据。';
  return [
    `目标商场总数：${stats.totalTarget}`,
    `缺口：${stats.gapCount} / 高潜：${stats.opportunityCount} / 排他：${stats.blockedCount}`,
    `已攻克：${stats.capturedCount}，蓝海：${stats.blueOceanCount}，中性：${stats.neutralCount}`,
  ].join('；');
};

const formatMallList = (malls: Mall[]) =>
  malls
    .slice(0, 20)
    .map(
      (m, idx) =>
        `${idx + 1}. [${m.city}] ${m.mallName}（${mapStatusLabel(m)}｜DJI${
          m.djiOpened ? '已开' : '未开'
        } / Insta${m.instaOpened ? '已开' : '未开'}）`,
    )
    .join('\n');

const stripCodeFences = (text?: string | null) => {
  if (!text) return '';
  return text.replace(/```json|```/gi, '').trim();
};

const extractRegionsFromText = (texts: string[], malls: Mall[]): Set<string> => {
  const regionSet = new Set<string>();
  const merged = texts.join(' ').trim();
  if (!merged) return regionSet;

  malls.forEach((m) => {
    const province = m.province || '';
    const city = m.city || '';
    const normProvince = normalizeRegion(province);
    const normCity = normalizeRegion(city);

    if (province && (merged.includes(province) || (normProvince && merged.includes(normProvince)))) {
      regionSet.add(province);
      if (normProvince) regionSet.add(normProvince);
    }
    if (city && (merged.includes(city) || (normCity && merged.includes(normCity)))) {
      regionSet.add(city);
      if (normCity) regionSet.add(normCity);
    }
  });
  return regionSet;
};

const scopeMallsByQuestion = (question: string, malls: Mall[], historyQuestions: string[] = []) => {
  const regions = extractRegionsFromText([question, ...historyQuestions], malls);
  if (!regions.size) {
    return { scopedMalls: malls, regions: [] as string[] };
  }
  const scoped = malls.filter((m) => {
    const province = m.province || '';
    const city = m.city || '';
    const normProvince = normalizeRegion(province);
    const normCity = normalizeRegion(city);
    return (
      regions.has(province) ||
      regions.has(city) ||
      (normProvince && regions.has(normProvince)) ||
      (normCity && regions.has(normCity))
    );
  });
  return { scopedMalls: scoped.length ? scoped : malls, regions: Array.from(regions) };
};

const buildStoreCountSummary = (question: string, malls: Mall[]): string => {
  if (!malls.length) return '';
  const brand = inferBrandFromQuestion(question);
  const formatBrandSummary = (target: 'DJI' | 'Insta360') => {
    const opened = pickOpenedMalls(malls, target);
    if (!opened.length) return `${target}：当前区域暂无开业门店，更多是潜在/未开机会`;
    const cityCounts: Record<string, number> = {};
    opened.forEach((m) => {
      const city = m.city || '未知城市';
      cityCounts[city] = (cityCounts[city] || 0) + 1;
    });
    const topCities = Object.entries(cityCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([city, count]) => (count > 1 ? `${city}(${count})` : city))
      .join('、');
    const examples = opened
      .slice(0, 3)
      .map((m) => `${m.city || '未知城市'}·${m.mallName}`)
      .join('、');
    return `${target}：开业门店 ${opened.length} 家${topCities ? `，主要在 ${topCities}` : ''}${
      examples ? `，示例：${examples}` : ''
    }`;
  };

  if (brand === 'DJI' || brand === 'Insta360') {
    return `门店数量：${formatBrandSummary(brand)}`;
  }
  const djiSummary = formatBrandSummary('DJI');
  const instaSummary = formatBrandSummary('Insta360');
  return `门店数量：${djiSummary}；${instaSummary}`;
};

const callLlm = async (payload: any): Promise<string | null> => {
  const bailianApiKey =
    import.meta.env.VITE_BAILIAN_API_KEY || import.meta.env.VITE_BAILIAN_API_KEY_PUBLIC;
  if (!bailianApiKey || typeof fetch === 'undefined') {
    console.error('[AI 助手] 缺少百炼 API Key');
    return null;
  }

  const baseUrl =
    import.meta.env.VITE_BAILIAN_BASE_URL || 'https://dashscope.aliyuncs.com/compatible-mode/v1';
  const model = import.meta.env.VITE_BAILIAN_MODEL || 'qwen-plus';
  const endpoint = `${baseUrl.replace(/\/$/, '')}/chat/completions`;

  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${bailianApiKey}`,
      },
      body: JSON.stringify({ model, ...payload }),
    });
    if (!resp.ok) {
      console.error('[AI 助手] LLM 请求失败', resp.status, await resp.text());
      return null;
    }
    const json = await resp.json();
    const content = json.choices?.[0]?.message?.content as string | undefined;
    return typeof content === 'string' ? content.trim() : null;
  } catch (err) {
    console.error('[AI 助手] LLM 请求异常', err);
    return null;
  }
};

export default function useAiAssistant() {
  const [sessions, setSessions] = useState<Session[]>([
    { id: 'session-1', name: '对话 1', createdAt: Date.now(), messages: [INITIAL_MESSAGE], lastQuestion: undefined },
  ]);
  const [activeSessionId, setActiveSessionId] = useState('session-1');
  const [reportOptions, setReportOptions] = useState<ReportOption[]>([]);
  const [reportContent, setReportContent] = useState('');
  const [contextSnapshot, setContextSnapshot] = useState<ContextSnapshot | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) || sessions[0],
    [sessions, activeSessionId],
  );
  const history = activeSession?.messages || [];
  const lastQuestion = activeSession?.lastQuestion || '';

  const recentDialog = useMemo(() => {
    const list = history.filter((m) => m.role === 'user' || m.role === 'assistant').slice(-10);
    return list;
  }, [history]);

  const recentUserQuestions = useMemo(
    () => recentDialog.filter((m) => m.role === 'user').map((m) => m.content),
    [recentDialog],
  );

  const persistMessages = (updater: (msgs: ChatMessage[]) => ChatMessage[]) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSessionId ? { ...s, messages: updater(s.messages) } : s)),
    );
  };

  const startNewSession = useCallback(() => {
    const nextId = `session-${sessions.length + 1}`;
    const newSession: Session = {
      id: nextId,
      name: `对话 ${sessions.length + 1}`,
      createdAt: Date.now(),
      messages: [INITIAL_MESSAGE],
    };
    setSessions((prev) => [...prev, newSession]);
    setActiveSessionId(nextId);
    setReportOptions([]);
    setReportContent('');
    setContextSnapshot(null);
  }, [sessions.length]);

  const loadSession = useCallback((sessionId: string) => {
    if (sessionId === activeSessionId) return;
    const target = sessions.find((s) => s.id === sessionId);
    if (!target) return;
    setActiveSessionId(sessionId);
    setReportOptions([]);
    setReportContent('');
    setContextSnapshot(null);
  }, [activeSessionId, sessions]);

  const resetConversation = useCallback(() => {
    startNewSession();
  }, [startNewSession]);

  const sendMessage = useCallback(
    async (question: string, currentMalls: Mall[], stats?: CompetitionStats) => {
      if (isGenerating) return;
      const text = (question || '').trim() || '帮我看看现在最值得关注的商场机会点？';
      const { scopedMalls, regions } = scopeMallsByQuestion(text, currentMalls, recentUserQuestions);
      const context: ContextSnapshot = { malls: scopedMalls, stats };
      setContextSnapshot(context);
      const brandPreference = inferBrandFromQuestion(text);
      const openedMalls = pickOpenedMalls(scopedMalls, brandPreference);
      const keyMalls = openedMalls.length ? openedMalls : pickTopMalls(scopedMalls);
      const countSummary = buildStoreCountSummary(text, scopedMalls);

      const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: 'user', content: text };
      const pendingId = `a-${Date.now()}`;
      const pendingMsg: ChatMessage = {
        id: pendingId,
        role: 'assistant',
        content: '我正在结合当前筛选数据分析，请稍等…',
        relatedData: keyMalls,
      };
      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId ? { ...s, lastQuestion: text, messages: [...s.messages, userMsg, pendingMsg] } : s,
        ),
      );
      setIsGenerating(true);

      const regionText = regions.length ? `【地域范围】识别到：${regions.join('、')}（如不符请补充）` : '';
      const contextText = [
        regionText,
        countSummary ? `【数量快照】${countSummary.replace(/^门店数量：/, '')}` : null,
        `【数据概况】${buildDataSnapshot(stats)}`,
        `【重点商场（最多 20 个）】\n${formatMallList(keyMalls)}`,
      ]
        .filter(Boolean)
        .join('\n');
      const historyText = recentDialog
        .map((m) => `${m.role === 'user' ? '用户' : '助手'}：${m.content}`)
        .join('\n');

      const systemPrompt =
        '你是一名线下商场与门店布局的业务分析助手。只使用提供的上下文数据回答，不要编造数据或新增城市、商场名称。优先给出已开业门店的数量与示例，不要把未开业的商场当作现有门店。回答需简洁、有行动性，输出 3-5 条编号建议，不使用 Markdown 标题。若数据不足以支持结论，应明确说明。所有结论仅引用给出的商场与状态，不要创造不存在的商场，也不要给与用户问题无关的泛化策略。';

      const payload = {
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'assistant', content: contextText },
          { role: 'assistant', content: `最近对话历史：\n${historyText || '（无历史）'}` },
          { role: 'user', content: text },
        ],
        temperature: 0.35,
      };

      try {
        const aiText = await callLlm(payload);
        const fallback = [
          countSummary || null,
          '1. 数据摘要：当前筛选范围内目标/缺口/高潜/排他情况已同步，可重点盯住缺口与目标商场。',
          `2. 优先商场：${keyMalls.slice(0, 3).map((m) => m.mallName).join('、') || '筛选范围暂无明显机会点'}`,
          '3. 执行动作：确认排他限制、与渠道伙伴沟通进入时序，并随时更新实际进度。',
        ]
          .filter(Boolean)
          .join('\n');
        const finalAnswer = aiText ? (countSummary ? `${countSummary}\n${aiText}` : aiText) : fallback;
        persistMessages((prev) =>
          prev.map((m) => (m.id === pendingId ? { ...m, content: finalAnswer, relatedData: keyMalls } : m)),
        );
      } catch (err) {
        console.error('[AI 助手] sendMessage error', err);
        persistMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? {
                  ...m,
                  content: '调用 AI 助手失败，请稍后再试，或调整筛选后重试。',
                }
              : m,
          ),
        );
      } finally {
        setIsGenerating(false);
      }
    },
    [isGenerating, recentDialog, activeSessionId, recentUserQuestions],
  );

  const generateReportOptions = useCallback(
    async (malls?: Mall[], stats?: CompetitionStats) => {
      if (isGenerating) return [];
      const question = lastQuestion || '';
      const { scopedMalls, regions } = scopeMallsByQuestion(
        question,
        malls || contextSnapshot?.malls || [],
        recentUserQuestions,
      );
      const scopedStats = stats || contextSnapshot?.stats;
      setContextSnapshot({ malls: scopedMalls, stats: scopedStats });
      const brandPreference = inferBrandFromQuestion(question);
      const openedMalls = pickOpenedMalls(scopedMalls, brandPreference);
      const keyMalls = openedMalls.length ? openedMalls : pickTopMalls(scopedMalls);
      const historyText = recentDialog
        .map((m) => `${m.role === 'user' ? '用户' : '助手'}：${m.content}`)
        .join('\n');
      setIsGenerating(true);

      const systemPrompt =
        '你是一名商业分析顾问。请基于提供的数据和对话，为 Markdown 报告推荐 3-4 个分析维度选项。只能输出 JSON 数组，字段：id、title、reason。所有选项必须与用户问题强相关，不要给泛化或无关的选项。不要输出多余文字。';
      const regionText = regions.length ? `地域范围：${regions.join('、')}（若不符请提示用户补充）` : '';
      const payload = {
        messages: [
          { role: 'system', content: systemPrompt },
          {
            role: 'assistant',
            content: `${regionText ? `${regionText}\n` : ''}数据概况：${buildDataSnapshot(scopedStats)}\n重点商场：\n${formatMallList(
              keyMalls,
            )}`,
          },
          { role: 'assistant', content: `最近对话：\n${historyText || '（无历史）'}` },
          {
            role: 'user',
            content: `围绕我的问题「${question || '当前机会点'}」，结合给出的商场数据，给 3-4 个报告维度（JSON 数组，字段 id/title/reason），不要出现无关维度。`,
          },
        ],
        temperature: 0.25,
      };

      try {
        const raw = await callLlm(payload);
        const cleaned = stripCodeFences(raw);
        const parsed = cleaned ? JSON.parse(cleaned) : [];
        const normalized: ReportOption[] = Array.isArray(parsed)
          ? parsed.map((opt: any, idx: number) => ({
              id: String(opt.id || idx + 1),
              title: String(opt.title || `选项 ${idx + 1}`),
              reason: typeof opt.reason === 'string' ? opt.reason : opt.description || '',
            }))
          : [];
        const fallback: ReportOption[] = [
          { id: 'gap', title: '缺口机会与进入时机', reason: `围绕「${question || '当前机会'}」梳理 DJI 已开/对手未开的商场优先级` },
          { id: 'target', title: '目标场攻坚路线图', reason: '梳理 Target 商场当前状态与推进动作' },
          { id: 'risk', title: '排他与风险预警', reason: '识别排他/对手已开的高风险商场' },
          { id: 'region', title: '重点城市组合策略', reason: '对高权重城市给出组合打法' },
        ];
        const result = normalized.length ? normalized.slice(0, 4) : fallback;
        setReportOptions(result);
        return result;
      } catch (err) {
        console.error('[AI 助手] generateReportOptions error', err);
        const fallback: ReportOption[] = [
          { id: 'gap', title: '缺口机会与进入时机', reason: `围绕「${question || '当前机会'}」梳理 DJI 已开/对手未开的商场优先级` },
          { id: 'target', title: '目标场攻坚路线图', reason: '梳理 Target 商场当前状态与推进动作' },
          { id: 'risk', title: '排他与风险预警', reason: '识别排他/对手已开的高风险商场' },
        ];
        setReportOptions(fallback);
        return fallback;
      } finally {
        setIsGenerating(false);
      }
    },
    [contextSnapshot, isGenerating, recentDialog, lastQuestion, recentUserQuestions],
  );

  const generateFinalReport = useCallback(
    async (selectedIds: string[], malls?: Mall[], stats?: CompetitionStats) => {
      if (isGenerating) return '';
      const question = lastQuestion || '当前机会点';
      const { scopedMalls, regions } = scopeMallsByQuestion(
        question,
        malls || contextSnapshot?.malls || [],
        recentUserQuestions,
      );
      const scopedStats = stats || contextSnapshot?.stats;
      setContextSnapshot({ malls: scopedMalls, stats: scopedStats });
      const brandPreference = inferBrandFromQuestion(question);
      const openedMalls = pickOpenedMalls(scopedMalls, brandPreference);
      const keyMalls = openedMalls.length ? openedMalls : pickTopMalls(scopedMalls);
      const selectedOptions = reportOptions.filter((opt) => selectedIds.includes(opt.id));
      setIsGenerating(true);

      const progressId = `progress-${Date.now()}`;
      const progressMsg: ChatMessage = {
        id: progressId,
        role: 'assistant',
        content: '终稿生成中，请稍等，大概 1 分钟…',
      };
      persistMessages((prev) => [...prev, progressMsg]);

      const systemPrompt =
        '你是资深线下零售战略顾问。请输出一份约 2000 字的 Markdown 报告，语气专业简洁，仅基于提供的数据，不得编造城市/商场/数据。必须包含：\n' +
        '1) # 执行摘要\n2) ## 数据概览与假设（需列出数据来源和假设）\n3) ## 分析主体（按选中维度分节，用 ### 标题）\n4) ## 风险与下一步行动（仅基于数据，若无数据则说明不足）\n5) ## 结论。\n' +
        '至少包含一张对比表格（Markdown 表格）。不要杜撰数据或城市，不要输出与问题无关的建议。';
      const regionText = regions.length ? `地域范围：${regions.join('、')}（若有遗漏请指出）\n` : '';
      const countSummary = buildStoreCountSummary(question, scopedMalls);

      const payload = {
        messages: [
          { role: 'system', content: systemPrompt },
          {
            role: 'assistant',
            content: `${regionText}数据概况：${buildDataSnapshot(scopedStats)}\n重点商场（Top20）：\n${formatMallList(
              keyMalls,
            )}`,
          },
          {
            role: 'assistant',
            content: `选中的维度：${selectedOptions
              .map((o) => `${o.title}${o.reason ? `（${o.reason}）` : ''}`)
              .join('；')}\n用户问题：${question}`,
          },
          {
            role: 'user',
            content:
              `请基于上述数据与维度，生成一份中文 Markdown 长文报告（约 2000 字），首行使用标题“# ${question} 分析报告”，包含表格、清单和明确的行动项，行动项只能基于当前数据。若数据不足请明确说明，不要编造。结尾给出 3-5 条可落地的下一步。${
                countSummary ? `\n可参考的门店数量提示：${countSummary.replace(/^门店数量：/, '')}` : ''
              }`,
          },
        ],
        temperature: 0.25,
      };

      try {
        const raw = await callLlm(payload);
        const text =
          raw ||
          `# ${question} 分析报告（草稿）\n\n## 数据概览\n${buildDataSnapshot(scopedStats)}\n\n## 重点商场\n${formatMallList(
            keyMalls,
          )}\n\n> AI 报告生成失败，请稍后重试。`;
        setReportContent(text);
        persistMessages((prev) =>
          prev.map((m) => (m.id === progressId ? { ...m, content: '终稿已生成，可在报告弹窗查看。' } : m)),
        );
        return text;
      } catch (err) {
        console.error('[AI 助手] generateFinalReport error', err);
        const fallback =
          `# ${question} 分析报告（草稿）\n\n## 数据概览\n${buildDataSnapshot(scopedStats)}\n\n## 重点商场\n${formatMallList(
            keyMalls,
          )}\n\n> AI 报告生成失败，请稍后重试。`;
        setReportContent(fallback);
        persistMessages((prev) =>
          prev.map((m) => (m.id === progressId ? { ...m, content: '终稿生成失败，请稍后重试。' } : m)),
        );
        return fallback;
      } finally {
        setIsGenerating(false);
      }
    },
    [contextSnapshot, isGenerating, reportOptions, lastQuestion, recentUserQuestions],
  );

  return {
    history,
    sessions,
    activeSessionId,
    startNewSession,
    loadSession,
    reportOptions,
    reportContent,
    isGenerating,
    sendMessage,
    generateReportOptions,
    generateFinalReport,
    resetConversation,
  };
}
