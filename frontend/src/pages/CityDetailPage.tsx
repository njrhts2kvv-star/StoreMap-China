import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Typography } from "antd";
import CitySummaryCard from "../components/CitySummaryCard";
import MallTable from "../components/MallTable";
import { CitySummary, MallInCity, fetchCities, fetchMallsInCity } from "../api/cities";

const { Title } = Typography;

const CityDetailPage = () => {
  const { cityCode } = useParams();
  const navigate = useNavigate();
  const [malls, setMalls] = useState<MallInCity[]>([]);
  const [cityMeta, setCityMeta] = useState<CitySummary | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!cityCode) return;
    const load = async () => {
      setLoading(true);
      try {
        const [mallData, cityList] = await Promise.all([
          fetchMallsInCity(cityCode, { order: "desc" }),
          fetchCities({ limit: 400 }),
        ]);
        setMalls(mallData);
        setCityMeta(cityList.find((c) => c.city_code === cityCode) || null);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [cityCode]);

  const summary = useMemo(() => {
    if (cityMeta) {
      return cityMeta;
    }
    if (!malls.length) {
      return null;
    }
    return {
      city_name: malls[0].city_name || cityCode || "",
      city_code: cityCode || "",
      province_name: "",
      city_tier: "",
      mall_count: malls.length,
      brand_count: malls.reduce((acc, mall) => acc + mall.total_brand_count, 0),
      luxury_brand_count: malls.reduce((acc, mall) => acc + mall.luxury_count, 0),
      outdoor_brand_count: malls.reduce((acc, mall) => acc + mall.outdoor_count, 0),
      electronics_brand_count: malls.reduce((acc, mall) => acc + mall.electronics_count, 0),
    } as CitySummary;
  }, [cityMeta, malls, cityCode]);

  return (
    <div>
      <div className="page-header">
        <Title level={3} style={{ margin: 0 }}>
          城市详情
        </Title>
      </div>

      {summary && (
        <CitySummaryCard
          cityName={summary.city_name}
          cityTier={summary.city_tier}
          mallCount={summary.mall_count}
          brandCount={summary.brand_count}
          luxuryCount={summary.luxury_brand_count}
          outdoorCount={summary.outdoor_brand_count}
          electronicsCount={summary.electronics_brand_count}
        />
      )}

      <div className="section">
        <MallTable
          loading={loading}
          data={malls}
          onSelect={(mallId) => navigate(`/malls/${mallId}`)}
        />
      </div>
    </div>
  );
};

export default CityDetailPage;
