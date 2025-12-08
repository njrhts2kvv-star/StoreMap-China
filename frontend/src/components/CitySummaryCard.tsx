import { Card, Col, Row, Statistic, Tag, Typography } from "antd";

interface Props {
  cityName: string;
  cityTier?: string;
  mallCount: number;
  brandCount: number;
  luxuryCount: number;
  outdoorCount: number;
  electronicsCount: number;
}

const tagColor: Record<string, string> = {
  luxury: "magenta",
  outdoor: "geekblue",
  electronics: "cyan",
};

const CitySummaryCard = ({
  cityName,
  cityTier,
  mallCount,
  brandCount,
  luxuryCount,
  outdoorCount,
  electronicsCount,
}: Props) => (
  <Card
    bordered={false}
    style={{
      background: "linear-gradient(135deg, rgba(59,130,246,0.15), rgba(14,165,233,0.12))",
      boxShadow: "0 10px 30px rgba(0,0,0,0.3)",
    }}
  >
    <Row gutter={16} align="middle">
      <Col span={8}>
        <Typography.Title level={4} style={{ color: "#e2e8f0", marginBottom: 4 }}>
          {cityName}
        </Typography.Title>
        <div className="subtle">城市等级: {cityTier || "未知"}</div>
      </Col>
      <Col span={4}>
        <Statistic title="商场数" value={mallCount} />
      </Col>
      <Col span={4}>
        <Statistic title="品牌数" value={brandCount} />
      </Col>
      <Col span={8} style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <Tag color={tagColor.luxury}>重奢 {luxuryCount}</Tag>
        <Tag color={tagColor.outdoor}>户外 {outdoorCount}</Tag>
        <Tag color={tagColor.electronics}>3C {electronicsCount}</Tag>
      </Col>
    </Row>
  </Card>
);

export default CitySummaryCard;
