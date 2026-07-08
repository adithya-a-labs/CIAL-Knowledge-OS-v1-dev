import { useState } from 'react';
import { Edit, CheckCircle, XCircle } from 'lucide-react';
import PageHeader from '@/components/common/PageHeader';
import StatusPill from '@/components/common/StatusPill';
import { AUDIT_LOG, MOCK_USERS } from '@/data/auditLogData';
import { CURRENT_USER } from '@/config/userConfig';
import { Role } from '@/types';
import { hasPermission } from '@/config/securityConfig';
import { INTEGRATIONS, ROLE_COLORS, THEME_CONFIG_ITEMS, INGESTION_SETTINGS } from '@/data/adminData';

type TabId = 'theme' | 'ingestion' | 'users' | 'audit' | 'integrations';

const TABS: { id: TabId; label: string }[] = [
  { id: 'theme', label: 'Theme' },
  { id: 'ingestion', label: 'Document Ingestion' },
  { id: 'users', label: 'User Roles' },
  { id: 'audit', label: 'Audit Log' },
  { id: 'integrations', label: 'Integrations' },
];

export default function AdminSettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('theme');
  const userRole = CURRENT_USER.role as Role;
  const canAccess = hasPermission(userRole, 'canAccessAdmin');

  if (!canAccess) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center" data-testid="access-denied">
        <div className="w-12 h-12 rounded-full bg-[#fdd8d8] flex items-center justify-center mb-3">
          <XCircle size={22} className="text-[#c0392b]" />
        </div>
        <p className="font-semibold text-[#1a2e14]">Access Denied</p>
        <p className="text-sm text-[#5a7a52] mt-1">You do not have permission to view this page.</p>
      </div>
    );
  }

  return (
    <div className="fluid-section" data-testid="admin-settings-page">
      <PageHeader title="Admin / Settings" subtitle="Manage system configuration." />

      {/* Tab Bar */}
      <div className="scrollbar-soft mb-5 flex gap-1 overflow-x-auto rounded-xl border border-[#e2eedd] bg-white p-1 shadow-sm">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? 'bg-[#4a7c3f] text-white shadow-sm'
                : 'text-[#5a7a52] hover:bg-[#f0f7ed]'
            }`}
            data-testid={`tab-${tab.id}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Theme Tab */}
      {activeTab === 'theme' && (
        <div className="fluid-grid" data-testid="tab-content-theme">
          {THEME_CONFIG_ITEMS.map(item => (
            <div key={item.label} className="fluid-card responsive-card min-w-0 border border-[#e2eedd] bg-white p-4 shadow-sm hover:shadow-md">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold text-[#5a7a52] uppercase tracking-wide">{item.label}</p>
                {item.type === 'swatch' && <div className="w-8 h-8 rounded-lg border" style={{ background: item.value }} />}
                {item.type === 'font' && <span className="text-sm font-semibold">Aa</span>}
                {item.type === 'logo' && <img src={item.value} alt="Logo" className="h-8 w-auto object-contain" />}
              </div>
              <p className="text-sm text-[#1a2e14] font-medium">{item.value}</p>
              <p className="text-xs text-[#9ab88e] mt-1">Coming soon — Configure</p>
              <button className="mt-2 text-xs text-[#4a7c3f] hover:underline font-medium">Configure</button>
            </div>
          ))}
        </div>
      )}

      {/* Document Ingestion Tab */}
      {activeTab === 'ingestion' && (
        <div className="fluid-grid" data-testid="tab-content-ingestion">
          {INGESTION_SETTINGS.map(item => (
            <div key={item.label} className="fluid-card responsive-card min-w-0 border border-[#e2eedd] bg-white p-4 shadow-sm hover:shadow-md">
              <p className="text-xs font-semibold text-[#5a7a52] uppercase tracking-wide mb-1.5">{item.label}</p>
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-[#1a2e14]">{item.value}</p>
                {item.type === 'toggle' && (
                  <div className="w-10 h-5 bg-[#4a7c3f] rounded-full relative cursor-pointer">
                    <div className="absolute right-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow-sm" />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* User Roles Tab */}
      {activeTab === 'users' && (
        <div className="scrollbar-soft responsive-card overflow-x-auto border border-[#e2eedd] bg-white shadow-sm" data-testid="tab-content-users">
          <table className="w-full min-w-[44rem]">
            <thead>
              <tr className="border-b border-[#e2eedd] bg-[#f8fdf6]">
                {['Name', 'Email', 'Role', 'Last Active', 'Actions'].map(h => (
                  <th key={h} className="text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wide px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MOCK_USERS.map((user, i) => (
                <tr key={i} className="border-b border-[#f0f7ed] hover:bg-[#f8fdf6] transition-colors" data-testid={`user-row-${i}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#4a7c3f] to-[#7ab648] flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <span className="text-sm font-medium text-[#1a2e14]">{user.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-[#5a7a52]">{user.email}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${ROLE_COLORS[user.role] || 'bg-gray-100 text-gray-600'}`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-[#5a7a52]">{user.lastActive}</td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 rounded-lg hover:bg-[#f0f7ed] text-[#5a7a52] hover:text-[#4a7c3f]" data-testid={`button-edit-user-${i}`}><Edit size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Audit Log Tab */}
      {activeTab === 'audit' && (
        <div className="responsive-card overflow-hidden border border-[#e2eedd] bg-white shadow-sm" data-testid="tab-content-audit">
          <div className="scrollbar-soft overflow-x-auto">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="border-b border-[#e2eedd] bg-[#f8fdf6]">
                  {['Timestamp', 'User', 'Action', 'Resource', 'IP Address', 'Status'].map(h => (
                    <th key={h} className="text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wide px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {AUDIT_LOG.map((log) => (
                  <tr key={log.id} className="border-b border-[#f0f7ed] hover:bg-[#f8fdf6] transition-colors" data-testid={`audit-row-${log.id}`}>
                    <td className="px-4 py-3 text-xs text-[#5a7a52] font-mono whitespace-nowrap">{log.timestamp}</td>
                    <td className="px-4 py-3 text-sm text-[#1a2e14]">{log.user}</td>
                    <td className="px-4 py-3 text-sm text-[#5a7a52]">{log.action}</td>
                    <td className="px-4 py-3 text-xs text-[#5a7a52] max-w-[200px] truncate">{log.resource}</td>
                    <td className="px-4 py-3 text-xs font-mono text-[#5a7a52]">{log.ip}</td>
                    <td className="px-4 py-3">
                      <StatusPill status={log.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Integrations Tab */}
      {activeTab === 'integrations' && (
        <div className="fluid-grid" data-testid="tab-content-integrations">
          {INTEGRATIONS.map((intg) => (
            <div key={intg.name} className="fluid-card responsive-card min-w-0 border border-[#e2eedd] bg-white p-4 shadow-sm hover:shadow-md">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[#1a2e14]">{intg.name}</p>
                  <p className="text-xs text-[#5a7a52] mt-0.5">Version: {intg.version}</p>
                  <p className="text-xs text-[#9ab88e] mt-0.5">Last sync: {intg.lastSync}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  {intg.status === 'Connected'
                    ? <CheckCircle size={14} className="text-[#27ae60]" />
                    : <XCircle size={14} className="text-[#c0392b]" />
                  }
                  <span className={`text-xs font-semibold ${intg.color}`}>{intg.status}</span>
                </div>
              </div>
              <button className="mt-3 w-full px-3 py-2 border border-[#ddecd6] text-sm text-[#4a7c3f] font-medium rounded-lg hover:bg-[#f0f7ed] transition-colors" data-testid={`button-configure-${intg.name.toLowerCase().replace(/\s+/g, '-').slice(0, 15)}`}>
                Configure Connection
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
