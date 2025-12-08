import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, Descriptions, Row, Space, Statistic, Typography } from "antd";
import MallBrandMatrix from "../components/MallBrandMatrix";
import { MallBrandMatrix as MallBrandMatrixType, MallDetail, fetchMallBrandMatrix, fetchMallDetail } from "../api/malls";

const { Title, Text } = Typography;

const MallDetailPage = () => {
  const { mallId } = useParams();
  const [detail, setDetail] = useState<MallDetail | null>(null);
  const [matrix, setMatrix] = useState<MallBrandMatrixType | null>(null);

  useEffect(() => {
    if (!mallId) return;
    const load = async () => {
      const [d, m] = await Promise.all([fetchMallDetail(mallId), fetchMallBrandMatrix(mallId)]);
      setDetail(d);
      setMatrix(m);
    };
    load();
  }, [mallId]);

  return (
    <div>
      <div className="page-header">
        <Title level={3} style={{ margin: 0 }}>
          商场详情
        </Title>
      </div>

      {detail && (
        <Card
          bordered={false}
          style={{ marginBottom: 16, background: "rgba(255,255,255,0.03)" }}
          title={
            <Space direction="vertical" size={0}>
              <Text style={{ color: "#e2e8f0", fontSize: 18 }}>{detail.name}</Text>
              <Text className="subtle">
                {detail.city_name} · {detail.mall_level || "未知等级"}
              </Text>
            </Space>
          }
        >
          <Descriptions column={2} size="small" labelStyle={{ color: "#cbd5e1" }}>
            <Descriptions.Item label="城市">{detail.city_name}</Descriptions.Item>
            <Descriptions.Item label="地址">{detail.address || "-"}</Descriptions.Item>
            <Descriptions.Item label="类别">{detail.mall_category || "-"}</Descriptions.Item>
            <Descriptions.Item label="POI">{detail.amap_poi_id || "-"}</Descriptions.Item>
          </Descriptions>
          <Row gutter={16} style={{ marginTop: 12 }}>
            <Statistic title="门店数" value={detail.store_count || 0} />
            <Statistic title="经度" value={detail.lng || 0} />
            <Statistic title="纬度" value={detail.lat || 0} />
          </Row>
        </Card>
      )}

      {matrix && (
        <Card
          bordered={false}
          style={{ background: "rgba(255,255,255,0.04)" }}
          title={`品牌矩阵 · 共 ${matrix.stats.total_brand_count || 0} 个品牌`}
        >
          <MallBrandMatrix brandsByCategory={matrix.brands_by_category} stats={matrix.stats} />
        </Card>
      )}
    </div>
  );
};

export default MallDetailPage;
