import { AppstoreOutlined, BankOutlined, ClusterOutlined } from "@ant-design/icons";
import { Layout, Menu, Space, Typography } from "antd";
import { BrowserRouter, Link, useLocation } from "react-router-dom";
import AppRouter from "./router";

const { Header, Content } = Layout;
const { Title } = Typography;

const Nav = () => {
  const location = useLocation();
  const activeKey = location.pathname.startsWith("/brands")
    ? "/brands"
    : location.pathname.startsWith("/malls")
    ? "/cities"
    : "/cities";

  return (
    <Menu
      theme="dark"
      mode="horizontal"
      selectedKeys={[activeKey]}
      items={[
        { key: "/cities", label: <Link to="/cities">城市视图</Link>, icon: <ClusterOutlined /> },
        { key: "/brands", label: <Link to="/brands">品牌视图</Link>, icon: <AppstoreOutlined /> },
      ]}
    />
  );
};

function App() {
  return (
    <BrowserRouter>
      <Layout style={{ minHeight: "100vh", background: "transparent" }}>
        <Header style={{ background: "rgba(11,23,42,0.8)", backdropFilter: "blur(10px)" }}>
          <Space align="center" style={{ width: "100%", justifyContent: "space-between" }}>
            <Space>
              <BankOutlined style={{ fontSize: 20, color: "#7dd3fc" }} />
              <Title level={4} style={{ color: "#e2e8f0", margin: 0 }}>
                品牌门店雷达
              </Title>
            </Space>
            <Nav />
          </Space>
        </Header>
        <Content>
          <div className="page">
            <AppRouter />
          </div>
        </Content>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
