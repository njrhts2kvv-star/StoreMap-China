import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, Descriptions, Select, Space, Statistic, Typography } from "antd";
import { BrandDetail, BrandStore, fetchBrandDetail, fetchBrandStores } from "../api/brands";
import BrandStoreTable from "../components/BrandStoreTable";

const { Title } = Typography;

const BrandDetailPage = () => {
  const { brandId } = useParams();
  const [detail, setDetail] = useState<BrandDetail | null>(null);
  const [stores, setStores] = useState<BrandStore[]>([]);
  const [cityFilter, setCityFilter] = useState<string | undefined>();
  const [loadingStores, setLoadingStores] = useState(false);

  useEffect(() => {
    if (!brandId) return;
    const loadBrand = async () => {
      const data = await fetchBrandDetail(brandId);
      setDetail(data);
    };
    loadBrand();
  }, [brandId]);

  useEffect(() => {
    if (!brandId) return;
    const loadStores = async () => {
      setLoadingStores(true);
      try {
        const params: Record<string, string | number | boolean> = { only_mall_store: true };
        if (cityFilter) params.city_code = cityFilter;
        const data = await fetchBrandStores(brandId, params);
        setStores(data);
      } finally {
        setLoadingStores(false);
      }
    };
    loadStores();
  }, [brandId, cityFilter]);

  const cityOptions = useMemo(
    () => {
      const map = new Map<string, string>();
      stores.forEach((s) => {
        if (s.city_code) {
          map.set(s.city_code, s.city_name || s.city_code);
        }
      });
      return Array.from(map.entries()).map(([value, label]) => ({ value, label }));
    },
    [stores]
  );

  return (
    <div>
      <div className="page-header">
        <Title level={3} style={{ margin: 0 }}>
          品牌详情
        </Title>
        <Space>
          <Select
            allowClear
            placeholder="按城市过滤"
            options={cityOptions}
            value={cityFilter}
            onChange={(val) => setCityFilter(val)}
            style={{ minWidth: 200 }}
          />
        </Space>
      </div>

      {detail && (
        <Card bordered={false} style={{ marginBottom: 16, background: "rgba(255,255,255,0.03)" }}>
          <Descriptions column={2} labelStyle={{ color: "#cbd5e1" }}>
            <Descriptions.Item label="品牌">{detail.name_cn}</Descriptions.Item>
            <Descriptions.Item label="英文">{detail.name_en || "-"}</Descriptions.Item>
            <Descriptions.Item label="类别">{detail.category || "-"}</Descriptions.Item>
            <Descriptions.Item label="Tier">{detail.tier || "-"}</Descriptions.Item>
            <Descriptions.Item label="国家">{detail.country_of_origin || "-"}</Descriptions.Item>
            <Descriptions.Item label="官网">{detail.official_url || "-"}</Descriptions.Item>
          </Descriptions>
          <Space size={24} style={{ marginTop: 12 }}>
            <Statistic title="门店" value={detail.aggregate_stats.store_count} />
            <Statistic title="城市" value={detail.aggregate_stats.city_count} />
            <Statistic title="商场" value={detail.aggregate_stats.mall_count} />
          </Space>
        </Card>
      )}

      <Card bordered={false} title="门店列表" style={{ background: "rgba(255,255,255,0.04)" }}>
        <BrandStoreTable data={stores} loading={loadingStores} />
      </Card>
    </div>
  );
};

export default BrandDetailPage;
