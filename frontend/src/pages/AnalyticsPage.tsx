import { TrendingUp, TrendingDown, Search, CheckCircle, HelpCircle, Star, Target, Users, BookOpen, GraduationCap } from 'lucide-react';
import { PieChart, Pie, Cell, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import PageHeader from '@/components/common/PageHeader';
import ChartCard from '@/components/common/ChartCard';
import { ANALYTICS_KPIS, TOP_CATEGORIES_DATA, QUERY_TREND_DATA, TOP_DEPARTMENTS_DATA, LEARNING_TREND_DATA } from '@/data/analyticsData';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  Search, CheckCircle, HelpCircle, Star, Target, Users, BookOpen, GraduationCap,
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-xs">
        <p className="font-semibold text-foreground mb-1">{label}</p>
        {payload.map((p: any) => (
          <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value}</p>
        ))}
      </div>
    );
  }
  return null;
};

const PieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  if (percent < 0.08) return null;
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

export default function AnalyticsPage() {
  return (
    <div className="fluid-section" data-testid="analytics-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Analytics</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Knowledge OS insights across search, learning, and coverage.</p>
        </div>
        <select className="text-sm bg-card border border-border rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-ring/30 self-start sm:self-auto" data-testid="filter-date-range">
          <option>Last 30 Days</option>
          <option>Last 7 Days</option>
          <option>Last 90 Days</option>
          <option>This Year</option>
        </select>
      </div>

      {/* KPI Cards — 2 rows of 4 */}
      <div className="fluid-grid-sm mb-5">
        {ANALYTICS_KPIS.map((kpi) => {
          const IconComp = ICON_MAP[kpi.icon] || Search;
          return (
            <div key={kpi.label} className="fluid-card responsive-card min-w-0 border border-border bg-card p-4 shadow-sm hover:shadow-md" data-testid={`analytics-kpi-${kpi.label.toLowerCase().replace(/\s+/g, '-')}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
                  <IconComp size={15} className="text-primary" />
                </div>
                <span className={`text-xs font-semibold flex items-center gap-0.5 ${kpi.trend === 'up' ? 'text-[#27ae60]' : kpi.trend === 'down' ? 'text-[#c0392b]' : 'text-muted-foreground'}`}>
                  {kpi.trend === 'up' ? <TrendingUp size={12} /> : kpi.trend === 'down' ? <TrendingDown size={12} /> : null}
                  {kpi.delta}
                </span>
              </div>
              <p className="safe-text text-xs font-medium text-muted-foreground">{kpi.label}</p>
              <p className="text-2xl font-bold text-foreground mt-0.5">{kpi.value}</p>
            </div>
          );
        })}
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 gap-4 mb-4 xl:grid-cols-2">
        {/* Donut / Pie Chart */}
        <ChartCard title="Top Query Categories" subtitle="Distribution by category — last 30 days">
          <div className="flex flex-col items-center gap-4 sm:flex-row">
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={TOP_CATEGORIES_DATA}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  labelLine={false}
                  label={PieLabel}
                >
                  {TOP_CATEGORIES_DATA.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => [`${value}%`, '']} />
              </PieChart>
            </ResponsiveContainer>
            <div className="w-full min-w-0 space-y-1.5 sm:w-44">
              {TOP_CATEGORIES_DATA.map((item) => (
                <div key={item.name} className="flex items-center gap-2" data-testid={`legend-${item.name.toLowerCase().replace(/\s+/g, '-').slice(0, 20)}`}>
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: item.fill }} />
                  <span className="text-xs text-foreground flex-1 truncate">{item.name}</span>
                  <span className="text-xs font-semibold text-muted-foreground">{item.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>

        {/* Line Chart */}
        <ChartCard title="Query Trend" subtitle="Total vs resolved queries over time">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={QUERY_TREND_DATA} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2eedd" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#5a7a52' }} />
              <YAxis tick={{ fontSize: 11, fill: '#5a7a52' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="total" name="Total Queries" stroke="#4a7c3f" strokeWidth={2.5} dot={{ r: 4, fill: '#4a7c3f' }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="resolved" name="Resolved Queries" stroke="#7ab648" strokeWidth={2.5} dot={{ r: 4, fill: '#7ab648' }} strokeDasharray="5 3" activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Top Departments */}
        <ChartCard title="Top Departments" subtitle="Query volume and resolution rate by department">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={TOP_DEPARTMENTS_DATA} margin={{ top: 5, right: 10, left: -10, bottom: 0 }} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e2eedd" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#5a7a52' }} />
              <YAxis dataKey="department" type="category" tick={{ fontSize: 11, fill: '#5a7a52' }} width={72} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="queries" name="Total Queries" fill="#4a7c3f" radius={[0, 4, 4, 0]} barSize={12} />
              <Bar dataKey="resolved" name="Resolved" fill="#7ab648" radius={[0, 4, 4, 0]} barSize={12} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Learning Completions Trend */}
        <ChartCard title="Learning Completions" subtitle="Course enrollments vs completions over time">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={LEARNING_TREND_DATA} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2eedd" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#5a7a52' }} />
              <YAxis tick={{ fontSize: 11, fill: '#5a7a52' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="enrolled" name="Enrolled" fill="#ddecd6" radius={[4, 4, 0, 0]} barSize={20} />
              <Bar dataKey="completions" name="Completions" fill="#4a7c3f" radius={[4, 4, 0, 0]} barSize={20} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
