import { useLocation } from 'wouter';
import StatCard from '@/components/common/StatCard';
import { DASHBOARD_KPI_STATS, KPI_ICON_BG } from '@/data/dashboardData';

export default function KpiRow() {
  const [, setLocation] = useLocation();

  return (
    <div className="fluid-grid-sm" data-testid="kpi-row">
      {DASHBOARD_KPI_STATS.map((stat) => (
        <StatCard
          key={stat.label}
          label={stat.label}
          value={stat.value}
          delta={stat.delta}
          trend={stat.trend}
          icon={stat.icon}
          iconBg={KPI_ICON_BG[stat.icon]}
          viewAllLink={stat.label === 'Unanswered Queries' ? '/queries' : undefined}
          onViewAll={stat.label === 'Unanswered Queries' ? () => setLocation('/admin') : undefined}
        />
      ))}
    </div>
  );
}
