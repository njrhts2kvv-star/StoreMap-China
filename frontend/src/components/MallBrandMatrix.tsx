import { Card, Col, Empty, Row, Tag, Typography } from "antd";
import { BrandInMall } from "../api/malls";

interface Props {
  brandsByCategory: Record<string, BrandInMall[]>;
  stats?: Record<string, number>;
}

const palette = ["#7dd3fc", "#fcd34d", "#f472b6", "#a78bfa", "#34d399", "#f97316"];

const MallBrandMatrix = ({ brandsByCategory, stats }: Props) => {
  const categories = Object.keys(brandsByCategory);

  if (!categories.length) {
    return <Empty description="暂无品牌数据" />;
  }

  return (
    <Row gutter={[12, 12]}>
      {categories.map((category, idx) => (
        <Col xs={24} sm={12} md={8} key={category}>
          <Card
            size="small"
            style={{
              minHeight: 180,
              borderColor: "rgba(255,255,255,0.08)",
              background: "rgba(255,255,255,0.03)",
            }}
            title={
              <Typography.Text style={{ color: palette[idx % palette.length] }}>
                {category} {stats && stats[`${category}_count`] ? `(${stats[`${category}_count`]})` : ""}
              </Typography.Text>
            }
          >
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {brandsByCategory[category].map((brand) => (
                <Tag
                  key={brand.brand_id}
                  color="cyan"
                  style={{ padding: "4px 8px", borderRadius: 16, fontWeight: 600 }}
                >
                  {brand.name_cn}
                  {brand.store_count > 1 ? ` x${brand.store_count}` : ""}
                </Tag>
              ))}
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  );
};

export default MallBrandMatrix;
