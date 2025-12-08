import { useEffect, useMemo, useState } from "react";
import { Input, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useNavigate } from "react-router-dom";
import { CitySummary, fetchCities } from "../api/cities";

const { Title } = Typography;

const CityListPage = () => {
  const [cities, setCities] = useState<CitySummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchCities({ limit: 200 });
        setCities(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filtered = useMemo(
    () => cities.filter((c) => c.city_name.toLowerCase().includes(keyword.toLowerCase())),
    [cities, keyword]
  );

  const columns: ColumnsType<CitySummary> = [
    { title: "城市", dataIndex: "city_name", key: "city_name" },
    { title: "等级", dataIndex: "city_tier", key: "city_tier", width: 100 },
    {
      title: "商场数",
      dataIndex: "mall_count",
      key: "mall_count",
      sorter: (a, b) => a.mall_count - b.mall_count,
      width: 110,
    },
    {
      title: "品牌数",
      dataIndex: "brand_count",
      key: "brand_count",
      sorter: (a, b) => a.brand_count - b.brand_count,
      width: 110,
    },
    {
      title: "重奢",
      dataIndex: "luxury_brand_count",
      key: "luxury_brand_count",
      sorter: (a, b) => a.luxury_brand_count - b.luxury_brand_count,
      width: 90,
      render: (val) => <Tag color="magenta">{val}</Tag>,
    },
    {
      title: "户外",
      dataIndex: "outdoor_brand_count",
      key: "outdoor_brand_count",
      sorter: (a, b) => a.outdoor_brand_count - b.outdoor_brand_count,
      width: 90,
      render: (val) => <Tag color="geekblue">{val}</Tag>,
    },
    {
      title: "3C",
      dataIndex: "electronics_brand_count",
      key: "electronics_brand_count",
      sorter: (a, b) => a.electronics_brand_count - b.electronics_brand_count,
      width: 90,
      render: (val) => <Tag color="cyan">{val}</Tag>,
    },
  ];

  return (
    <div>
      <div className="page-header">
        <Title level={3} style={{ margin: 0 }}>
          城市视图
        </Title>
        <Space>
          <Input.Search
            placeholder="搜索城市"
            allowClear
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 240 }}
          />
        </Space>
      </div>

      <Table<CitySummary>
        rowKey="city_code"
        loading={loading}
        columns={columns}
        dataSource={filtered}
        onRow={(record) => ({
          onClick: () => navigate(`/cities/${record.city_code}`),
          style: { cursor: "pointer" },
        })}
        pagination={{ pageSize: 20 }}
      />
    </div>
  );
};

export default CityListPage;
