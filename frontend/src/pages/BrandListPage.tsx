import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input, Select, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { BrandItem, fetchBrands } from "../api/brands";

const { Title } = Typography;

const BrandListPage = () => {
  const [brands, setBrands] = useState<BrandItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string[]>([]);
  const [tierFilter, setTierFilter] = useState<string[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const params: Record<string, string> = {};
        if (categoryFilter.length) params.category = categoryFilter.join(",");
        if (tierFilter.length) params.tier = tierFilter.join(",");
        const data = await fetchBrands(params);
        setBrands(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [categoryFilter, tierFilter]);

  const filtered = useMemo(
    () => brands.filter((b) => b.name_cn.toLowerCase().includes(keyword.toLowerCase())),
    [brands, keyword]
  );

  const columns: ColumnsType<BrandItem> = [
    { title: "中文名", dataIndex: "name_cn", key: "name_cn" },
    { title: "英文名", dataIndex: "name_en", key: "name_en" },
    { title: "Category", dataIndex: "category", key: "category", width: 140 },
    { title: "Tier", dataIndex: "tier", key: "tier", width: 140 },
    { title: "Origin", dataIndex: "country_of_origin", key: "country_of_origin", width: 100 },
    { title: "数据状态", dataIndex: "data_status", key: "data_status", width: 120 },
  ];

  const categoryOptions = Array.from(new Set(brands.map((b) => b.category).filter(Boolean))).map((c) => ({
    label: c,
    value: c as string,
  }));
  const tierOptions = Array.from(new Set(brands.map((b) => b.tier).filter(Boolean))).map((t) => ({
    label: t,
    value: t as string,
  }));

  return (
    <div>
      <div className="page-header">
        <Title level={3} style={{ margin: 0 }}>
          品牌视图
        </Title>
        <Space>
          <Select
            mode="multiple"
            allowClear
            placeholder="按品类"
            options={categoryOptions}
            value={categoryFilter}
            onChange={setCategoryFilter}
            style={{ minWidth: 200 }}
          />
          <Select
            mode="multiple"
            allowClear
            placeholder="按 tier"
            options={tierOptions}
            value={tierFilter}
            onChange={setTierFilter}
            style={{ minWidth: 200 }}
          />
          <Input.Search
            placeholder="搜索品牌"
            allowClear
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 220 }}
          />
        </Space>
      </div>

      <Table<BrandItem>
        rowKey="brand_id"
        loading={loading}
        columns={columns}
        dataSource={filtered}
        onRow={(record) => ({
          onClick: () => navigate(`/brands/${record.brand_id}`),
          style: { cursor: "pointer" },
        })}
        pagination={{ pageSize: 20 }}
      />
    </div>
  );
};

export default BrandListPage;
