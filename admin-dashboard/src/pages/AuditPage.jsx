import { useState, useEffect } from 'react';
import { Shield, Search, Filter, RefreshCw, AlertTriangle, Activity, Users } from 'lucide-react';
import { audit as auditApi } from '../services/api';

export default function AuditPage() {
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    loadData();
  }, [page]);

  const loadData = async () => {
    setLoading(true);
    try {
      const params = { page, limit: 30 };
      if (filter) params.action = filter;

      const [logData, summaryData] = await Promise.all([
        auditApi.list(params),
        auditApi.summary(),
      ]);
      setLogs(logData.items || []);
      setTotalPages(logData.total_pages || 1);
      setSummary(summaryData);
    } catch (err) {
      console.error('Failed to load audit data:', err);
    }
    setLoading(false);
  };

  const getActionColor = (action) => {
    if (action.includes('login')) return '#3b82f6';
    if (action.includes('register')) return '#059669';
    if (action.includes('sos')) return '#ef4444';
    if (action.includes('create')) return '#8b5cf6';
    if (action.includes('update') || action.includes('assign')) return '#f59e0b';
    if (action.includes('delete') || action.includes('dismiss')) return '#ef4444';
    if (action.includes('broadcast')) return '#ec4899';
    if (action.includes('prediction')) return '#6366f1';
    return 'var(--text-muted)';
  };

  const getActionIcon = (action) => {
    if (action.includes('sos')) return '🆘';
    if (action.includes('broadcast')) return '📡';
    if (action.includes('prediction')) return '🔮';
    if (action.includes('login')) return '🔑';
    if (action.includes('create')) return '✨';
    if (action.includes('assign')) return '🤝';
    return '📋';
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title"><Shield size={28} style={{ marginRight: 8 }} /> Audit Trail</h1>
          <p className="page-subtitle">Complete activity log and security monitoring</p>
        </div>
        <button className="btn btn-secondary" onClick={loadData}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }}>
          <div className="card" style={{ textAlign: 'center' }}>
            <Activity size={24} style={{ color: '#3b82f6', marginBottom: 8 }} />
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)' }}>{summary.actions_today}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Actions Today</div>
          </div>
          <div className="card" style={{ textAlign: 'center' }}>
            <Users size={24} style={{ color: '#059669', marginBottom: 8 }} />
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)' }}>{summary.top_actors?.length || 0}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Active Users</div>
          </div>
          <div className="card" style={{ textAlign: 'center', ...(summary.suspicious_activity?.length > 0 ? { border: '2px solid #ef4444', background: 'rgba(239,68,68,0.05)' } : {}) }}>
            <AlertTriangle size={24} style={{ color: summary.suspicious_activity?.length > 0 ? '#ef4444' : '#f59e0b', marginBottom: 8 }} />
            <div style={{ fontSize: 28, fontWeight: 700, color: summary.suspicious_activity?.length > 0 ? '#ef4444' : 'var(--text-primary)' }}>
              {summary.suspicious_activity?.length || 0}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Suspicious Events</div>
          </div>
        </div>
      )}

      {/* Top Actors */}
      {summary?.top_actors?.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 12, fontSize: 14, fontWeight: 600, color: 'var(--text-muted)' }}>Most Active Users Today</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {summary.top_actors.map((actor, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 14px', borderRadius: 20, background: 'var(--bg-tertiary)', fontSize: 13 }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'var(--gradient-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 10, fontWeight: 700 }}>
                  {actor.user_name?.[0] || '?'}
                </div>
                <span style={{ fontWeight: 500 }}>{actor.user_name}</span>
                <span style={{ color: 'var(--text-muted)' }}>({actor.action_count})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            className="input"
            placeholder="Filter by action type (e.g., sos, login, prediction)"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && loadData()}
            style={{ paddingLeft: 36 }}
          />
        </div>
        <button className="btn btn-secondary" onClick={() => { setFilter(''); setPage(1); loadData(); }}>
          <Filter size={14} /> Clear
        </button>
      </div>

      {/* Audit Log Table */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading audit trail...</div>
      ) : (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border-color)' }}>
                <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Time</th>
                <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>User</th>
                <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Action</th>
                <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Entity</th>
                <th style={{ textAlign: 'left', padding: '10px 12px', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, i) => (
                <tr key={log.id || i} style={{ borderBottom: '1px solid var(--border-color)', transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-tertiary)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ padding: '10px 12px', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontSize: 12 }}>
                    {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'var(--accent-green)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 9, fontWeight: 700 }}>
                        {(log.user_name || '?')[0].toUpperCase()}
                      </div>
                      <span style={{ fontWeight: 500 }}>{log.user_name || 'System'}</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 500, background: `${getActionColor(log.action)}15`, color: getActionColor(log.action) }}>
                      {getActionIcon(log.action)} {log.action}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 12 }}>
                    {log.entity_type && <span>{log.entity_type}{log.entity_id ? ` #${log.entity_id.slice(0, 8)}` : ''}</span>}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 11, fontFamily: 'monospace' }}>
                    {log.ip_address || '—'}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No audit records found</td></tr>
              )}
            </tbody>
          </table>

          {/* Pagination */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-color)' }}>
            <button className="btn btn-secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={{ padding: '4px 16px', fontSize: 12 }}>← Prev</button>
            <span style={{ alignSelf: 'center', fontSize: 13, color: 'var(--text-muted)' }}>Page {page} of {totalPages}</span>
            <button className="btn btn-secondary" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} style={{ padding: '4px 16px', fontSize: 12 }}>Next →</button>
          </div>
        </div>
      )}
    </div>
  );
}
