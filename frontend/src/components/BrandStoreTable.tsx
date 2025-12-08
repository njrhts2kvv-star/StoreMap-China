import { Badge, Table } from "antd";
import { ColumnsType } from "antd/es/table";
import { BrandStore } from "../api/brands";

interface Props {
  data: BrandStore[];
  loading?: boolean;
}

const BrandStoreTable = ({ data, loading }: Props) => {
  const columns: ColumnsType<BrandStore> = [
    { title: "城市", dataIndex: "city_name", key: "city_name", width: 140 },
    { title: "商场", dataIndex: "mall_name", key: "mall_name", width: 200 },
    { title: "门店类型", dataIndex: "store_type_std", key: "store_type_std", width: 120 },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value) => <Badge status={value === "open" ? "success" : "default"} text={value} />,
    },
    { title: "地址", dataIndex: "address_std", key: "address_std" },
    { title: "开业时间", dataIndex: "opened_at", key: "opened_at", width: 140 },
  ];

  return (
    <Table<BrandStore>
      rowKey="store_id"
      loading={loading}
      columns={columns}
      dataSource={data}
      size="small"
      pagination={{ pageSize: 20 }}
    />
  );
};

export default BrandStoreTable;
