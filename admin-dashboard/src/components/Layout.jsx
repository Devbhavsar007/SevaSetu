import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useState, useEffect } from 'react';
import { LayoutDashboard, ClipboardList, Map, Users, BrainCircuit, ScanLine, Radio, Sun, Moon, Package, Shield, LogOut } from 'lucide-react';
import DisasterAlertSystem from './DisasterAlertSystem';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/needs', icon: ClipboardList, label: 'Need Tracker' },
  { path: '/map', icon: Map, label: 'Live Map' },
  { path: '/volunteers', icon: Users, label: 'Volunteers' },
  { path: '/matching', icon: BrainCircuit, label: 'Smart Match' },
  { path: '/ocr', icon: ScanLine, label: 'OCR Scanner' },
  { path: '/broadcast', icon: Radio, label: 'Broadcast' },
  { path: '/inventory', icon: Package, label: 'Inventory' },
  { path: '/audit', icon: Shield, label: 'Audit Trail' },
];

export default function Layout() {
  const { user } = useAuth();
  const [theme, setTheme] = useState(() => localStorage.getItem('sa-theme') || 'light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('sa-theme', theme);
  }, [theme]);

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo" style={{ padding: '20px 10px' }}>
          <img
            src="/LOGO.png"
            alt="SevaSetu"
            style={{
              width: '100%',
              maxWidth: '260px',
              height: 'auto',
              objectFit: 'contain',
              imageRendering: '-webkit-optimize-contrast',
              display: 'block',
              margin: '0 auto',
              transform: 'scale(1.3)',
            }}
          />
        </div>

        <nav className="sidebar-nav">
          {navItems.map(item => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon className="nav-icon" size={20} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          {/* External Link */}
          <a 
            href="https://sevasetu-landing.onrender.com" 
            style={{ 
              display: 'flex', alignItems: 'center', gap: '10px', 
              padding: '10px', marginBottom: '16px', borderRadius: '8px',
              background: 'rgba(5, 150, 105, 0.1)', color: 'var(--accent-green)',
              fontSize: '13px', fontWeight: 600, textDecoration: 'none',
              border: '1px solid rgba(5, 150, 105, 0.2)'
            }}
          >
            <LayoutDashboard size={16} />
            Go to Website
          </a>

          {/* Theme Toggle */}
          <div className="theme-toggle">
            <button
              className={theme === 'light' ? 'active' : ''}
              onClick={() => setTheme('light')}
            >
              <Sun size={14} style={{ marginRight: '6px' }} /> Light
            </button>
            <button
              className={theme === 'dark' ? 'active' : ''}
              onClick={() => setTheme('dark')}
            >
              <Moon size={14} style={{ marginRight: '6px' }} /> Dark
            </button>
          </div>

          {/* User Info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              background: 'var(--gradient-primary)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '14px', fontWeight: 700, color: '#fff'
            }}>
              {user?.name?.[0] || 'A'}
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{user?.name || 'Admin'}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{user?.role || 'admin'}</div>
            </div>
            <button
              onClick={() => {
                if (window.confirm('Are you sure you want to logout?')) {
                  const { logout } = require('../context/AuthContext');
                }
              }}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text-muted)', padding: '6px',
                borderRadius: '6px', display: 'flex', alignItems: 'center',
              }}
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
      <DisasterAlertSystem />
    </div>
  );
}
