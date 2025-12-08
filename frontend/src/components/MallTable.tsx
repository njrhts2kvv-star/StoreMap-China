import { Table, Tag } from "antd";
import { ColumnsType } from "antd/es/table";
import { MallInCity } from "../api/cities";

interface Props {
  loading?: boolean;
  data: MallInCity[];
  onSelect?: (mallId: number) => void;
}

const MallTable = ({ loading, data, onSelect }: Props) => {
  const columns: ColumnsType<MallInCity> = [
    { title: "商场名", dataIndex: "name", key: "name" },
    { title: "等级", dataIndex: "mall_level", key: "mall_level", width: 90 },
    {
      title: "重奢",
      dataIndex: "luxury_count",
      key: "luxury_count",
      sorter: (a, b) => a.luxury_count - b.luxury_count,
      width: 90,
    },
    {
      title: "轻奢",
      dataIndex: "light_luxury_count",
      key: "light_luxury_count",
      sorter: (a, b) => a.light_luxury_count - b.light_luxury_count,
      width: 90,
    },
    {
      title: "户外",
      dataIndex: "outdoor_count",
      key: "outdoor_count",
      sorter: (a, b) => a.outdoor_count - b.outdoor_count,
      width: 90,
    },
    {
      title: "3C",
      dataIndex: "electronics_count",
      key: "electronics_count",
      sorter: (a, b) => a.electronics_count - b.electronics_count,
      width: 90,
    },
    {
      title: "品牌总数",
      dataIndex: "total_brand_count",
      key: "total_brand_count",
      sorter: (a, b) => a.total_brand_count - b.total_brand_count,
      width: 120,
    },
    {
      title: "类型",
      dataIndex: "mall_category",
      key: "mall_category",
      render: (value) => (value ? <Tag color="blue">{value}</Tag> : "-"),
      width: 120,
    },
  ];

  return (
    <Table<MallInCity>
      rowKey="mall_id"
      loading={loading}
      columns={columns}
      dataSource={data}
      pagination={false}
      onRow={(record) => ({
        onClick: () => onSelect?.(record.mall_id),
        style: { cursor: "pointer" },
      })}
    />
  );
};

export default MallTable;
