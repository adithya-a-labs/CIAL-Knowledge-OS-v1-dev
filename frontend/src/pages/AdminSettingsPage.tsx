import { useEffect, useRef, useState } from 'react';
import { Edit, CheckCircle, XCircle, FolderOpen, Save, RefreshCw } from 'lucide-react';
import PageHeader from '@/components/common/PageHeader';
import StatusPill from '@/components/common/StatusPill';
import { AUDIT_LOG, MOCK_USERS } from '@/data/auditLogData';
import { useAuth } from '@/auth/AuthContext';
import { Role } from '@/types';
import { hasPermission } from '@/config/securityConfig';
import { INTEGRATIONS, ROLE_COLORS, THEME_CONFIG_ITEMS, INGESTION_SETTINGS } from '@/data/adminData';
import {
  getEnterpriseRepositorySettings,
  saveEnterpriseRepository,
  validateEnterpriseRepository,
} from '@/api/client';
import type { EnterpriseRepositorySettings } from '@/api/types';

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
  const [repositoryFolder, setRepositoryFolder] = useState('');
  const [repositoryStatus, setRepositoryStatus] = useState<EnterpriseRepositorySettings | null>(null);
  const [repositoryMessage, setRepositoryMessage] = useState('');
  const [repositoryBusy, setRepositoryBusy] = useState(false);
  const directoryInputRef = useRef<HTMLInputElement | null>(null);
  const { userView } = useAuth();
  const userRole = (userView?.role ?? 'viewer') as Role;
  const canAccess = hasPermission(userRole, 'canAccessAdmin');

  useEffect(() => {
    if (!canAccess) return;
    let cancelled = false;
    getEnterpriseRepositorySettings()
      .then(settings => {
        if (cancelled) return;
        setRepositoryFolder(settings.folder);
        setRepositoryStatus(settings);
        setRepositoryMessage(settings.message);
      })
      .catch(error => {
        if (!cancelled) {
          setRepositoryMessage(error instanceof Error ? error.message : 'Unable to load repository settings.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [canAccess]);

  const handleValidateRepository = async () => {
    setRepositoryBusy(true);
    try {
      const result = await validateEnterpriseRepository({ folder: repositoryFolder });
      setRepositoryStatus(result);
      setRepositoryFolder(result.folder);
      setRepositoryMessage(result.message);
    } catch (error) {
      setRepositoryMessage(error instanceof Error ? error.message : 'Repository validation failed.');
    } finally {
      setRepositoryBusy(false);
    }
  };

  const handleSaveRepository = async () => {
    setRepositoryBusy(true);
    try {
      const result = await saveEnterpriseRepository({ folder: repositoryFolder });
      setRepositoryStatus(result);
      setRepositoryFolder(result.folder);
      setRepositoryMessage(result.message);
    } catch (error) {
      setRepositoryMessage(error instanceof Error ? error.message : 'Repository setting was not saved.');
    } finally {
      setRepositoryBusy(false);
    }
  };

  if (!canAccess) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center" data-testid="access-denied">
        <div className="w-12 h-12 rounded-full bg-destructive/15 flex items-center justify-center mb-3">
          <XCircle size={22} className="text-[#c0392b]" />
        </div>
        <p className="font-semibold text-foreground">Access Denied</p>
        <p className="text-sm text-muted-foreground mt-1">You do not have permission to view this page.</p>
      </div>
    );
  }

  return (
    <div className="fluid-section" data-testid="admin-settings-page">
      <PageHeader title="Admin / Settings" subtitle="Manage system configuration." />

      {/* Tab Bar */}
      <div className="scrollbar-soft mb-5 flex gap-1 overflow-x-auto rounded-xl border border-border bg-card p-1 shadow-sm">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? 'bg-[#4a7c3f] text-white shadow-sm'
                : 'text-muted-foreground hover:bg-accent'
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
            <div key={item.label} className="fluid-card responsive-card min-w-0 border border-border bg-card p-4 shadow-sm hover:shadow-md">
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{item.label}</p>
                {item.type === 'swatch' && <div className="w-8 h-8 rounded-lg border" style={{ background: item.value }} />}
                {item.type === 'font' && <span className="text-sm font-semibold">Aa</span>}
                {item.type === 'logo' && <img src={item.value} alt="Logo" className="h-8 w-auto object-contain" />}
              </div>
              <p className="text-sm text-foreground font-medium">{item.value}</p>
              <p className="text-xs text-[#9ab88e] mt-1">Coming soon — Configure</p>
              <button className="mt-2 text-xs text-primary hover:underline font-medium">Configure</button>
            </div>
          ))}
        </div>
      )}

      {/* Document Ingestion Tab */}
      {activeTab === 'ingestion' && (
        <div className="space-y-5" data-testid="tab-content-ingestion">
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                  Enterprise Knowledge Repository
                </p>
                <label htmlFor="enterprise-repository-folder" className="text-xs font-medium text-muted-foreground">
                  Folder
                </label>
                <input
                  id="enterprise-repository-folder"
                  value={repositoryFolder}
                  onChange={event => setRepositoryFolder(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                  placeholder="D:\\CIAL\\KnowledgeRepository"
                  data-testid="input-enterprise-repository-folder"
                />
                <input
                  ref={directoryInputRef}
                  type="file"
                  className="hidden"
                  // @ts-expect-error Browser directory selection is intentionally non-standard.
                  webkitdirectory=""
                  directory=""
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => directoryInputRef.current?.click()}
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-accent"
                  data-testid="button-browse-enterprise-repository"
                >
                  <FolderOpen size={16} />
                  Browse...
                </button>
                <button
                  type="button"
                  onClick={handleValidateRepository}
                  disabled={repositoryBusy}
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid="button-validate-enterprise-repository"
                >
                  <RefreshCw size={16} />
                  Validate
                </button>
                <button
                  type="button"
                  onClick={handleSaveRepository}
                  disabled={repositoryBusy}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#4a7c3f] px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#3d6834] disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid="button-save-enterprise-repository"
                >
                  <Save size={16} />
                  Save
                </button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              {repositoryStatus?.valid ? (
                <CheckCircle size={14} className="text-[#27ae60]" />
              ) : (
                <XCircle size={14} className="text-[#c0392b]" />
              )}
              <span className={repositoryStatus?.valid ? 'font-medium text-primary' : 'font-medium text-[#c0392b]'}>
                {repositoryMessage || 'Repository status unavailable.'}
              </span>
              {repositoryStatus && (
                <span className="text-muted-foreground">
                  Read {repositoryStatus.readable ? 'OK' : 'blocked'} / Write {repositoryStatus.writable ? 'OK' : 'blocked'}
                </span>
              )}
            </div>
          </div>

          <div className="fluid-grid">
            {INGESTION_SETTINGS.map(item => (
              <div key={item.label} className="fluid-card responsive-card min-w-0 border border-border bg-card p-4 shadow-sm hover:shadow-md">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">{item.label}</p>
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-foreground">{item.value}</p>
                  {item.type === 'toggle' && (
                    <div className="w-10 h-5 bg-[#4a7c3f] rounded-full relative cursor-pointer">
                      <div className="absolute right-0.5 top-0.5 w-4 h-4 bg-card rounded-full shadow-sm" />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* User Roles Tab */}
      {activeTab === 'users' && (
        <div className="scrollbar-soft responsive-card overflow-x-auto border border-border bg-card shadow-sm" data-testid="tab-content-users">
          <table className="w-full min-w-[44rem]">
            <thead>
              <tr className="border-b border-border bg-muted">
                {['Name', 'Email', 'Role', 'Last Active', 'Actions'].map(h => (
                  <th key={h} className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MOCK_USERS.map((user, i) => (
                <tr key={i} className="border-b border-border hover:bg-muted transition-colors" data-testid={`user-row-${i}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#4a7c3f] to-[#7ab648] flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
                        {user.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <span className="text-sm font-medium text-foreground">{user.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">{user.email}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${ROLE_COLORS[user.role] || 'bg-muted text-muted-foreground'}`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{user.lastActive}</td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary" data-testid={`button-edit-user-${i}`}><Edit size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Audit Log Tab */}
      {activeTab === 'audit' && (
        <div className="responsive-card overflow-hidden border border-border bg-card shadow-sm" data-testid="tab-content-audit">
          <div className="scrollbar-soft overflow-x-auto">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="border-b border-border bg-muted">
                  {['Timestamp', 'User', 'Action', 'Resource', 'IP Address', 'Status'].map(h => (
                    <th key={h} className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {AUDIT_LOG.map((log) => (
                  <tr key={log.id} className="border-b border-border hover:bg-muted transition-colors" data-testid={`audit-row-${log.id}`}>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono whitespace-nowrap">{log.timestamp}</td>
                    <td className="px-4 py-3 text-sm text-foreground">{log.user}</td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">{log.action}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground max-w-[200px] truncate">{log.resource}</td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{log.ip}</td>
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
            <div key={intg.name} className="fluid-card responsive-card min-w-0 border border-border bg-card p-4 shadow-sm hover:shadow-md">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">{intg.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Version: {intg.version}</p>
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
              <button className="mt-3 w-full px-3 py-2 border border-border text-sm text-primary font-medium rounded-lg hover:bg-accent transition-colors" data-testid={`button-configure-${intg.name.toLowerCase().replace(/\s+/g, '-').slice(0, 15)}`}>
                Configure Connection
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
