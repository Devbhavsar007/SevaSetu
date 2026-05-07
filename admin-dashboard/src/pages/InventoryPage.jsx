import { useState, useEffect } from 'react';
import { Package, Plus, AlertTriangle, TrendingDown, MapPin, Search } from 'lucide-react';
import { inventory as inventoryApi } from '../services/api';

export default function InventoryPage() {
  const [inventories, setInventories] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ name: '', latitude: 19.076, longitude: 72.878, address: '' });
  const [addItemForm, setAddItemForm] = useState({ category: 'food', item_name: '', quantity: 0, unit: 'units', minimum_threshold: 10 });
  const [selectedInventory, setSelectedInventory] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [invData, alertData] = await Promise.all([
        inventoryApi.list(),
        inventoryApi.getAlerts(),
      ]);
      setInventories(invData);
      setAlerts(alertData);
    } catch (err) {
      console.error('Failed to load inventory:', err);
    }
    setLoading(false);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await inventoryApi.create(createForm);
      setShowCreate(false);
      setCreateForm({ name: '', latitude: 19.076, longitude: 72.878, address: '' });
      loadData();
    } catch (err) {
      alert('Failed to create: ' + err.message);
    }
  };

  const handleAddItem = async (e) => {
    e.preventDefault();
    if (!selectedInventory) return;
    try {
      await inventoryApi.addItem(selectedInventory, addItemForm);
      setAddItemForm({ category: 'food', item_name: '', quantity: 0, unit: 'units', minimum_threshold: 10 });
      loadData();
    } catch (err) {
      alert('Failed to add item: ' + err.message);
    }
  };

  const handleAdjust = async (itemId, change) => {
    try {
      await inventoryApi.adjustItem(itemId, { quantity_change: change });
      loadData();
    } catch (err) {
      alert('Adjustment failed: ' + err.message);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title"><Package size={28} style={{ marginRight: 8 }} /> Resource Inventory</h1>
          <p className="page-subtitle">Track supplies, equipment, and resources across locations</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={16} /> New Warehouse
        </button>
      </div>

      {/* Low Stock Alerts */}
      {alerts.length > 0 && (
        <div className="card" style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.3)', marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <AlertTriangle size={20} style={{ color: '#ef4444' }} />
            <span style={{ fontWeight: 600, color: '#ef4444' }}>Low Stock Alerts ({alerts.length})</span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {alerts.map(item => (
              <span key={item.id} className="badge" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', padding: '4px 12px', borderRadius: 20 }}>
                <TrendingDown size={12} style={{ marginRight: 4 }} />
                {item.item_name}: {item.quantity}/{item.minimum_threshold} {item.unit}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Create Warehouse Modal */}
      {showCreate && (
        <div className="card" style={{ marginBottom: 24, border: '2px solid var(--accent-green)' }}>
          <h3 style={{ marginBottom: 16 }}>Create Warehouse/Stock Point</h3>
          <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <input className="input" placeholder="Name (e.g., Mumbai Central Warehouse)" value={createForm.name}
              onChange={e => setCreateForm({ ...createForm, name: e.target.value })} required />
            <input className="input" placeholder="Address" value={createForm.address}
              onChange={e => setCreateForm({ ...createForm, address: e.target.value })} />
            <input className="input" type="number" step="any" placeholder="Latitude" value={createForm.latitude}
              onChange={e => setCreateForm({ ...createForm, latitude: parseFloat(e.target.value) })} />
            <input className="input" type="number" step="any" placeholder="Longitude" value={createForm.longitude}
              onChange={e => setCreateForm({ ...createForm, longitude: parseFloat(e.target.value) })} />
            <div style={{ gridColumn: 'span 2', display: 'flex', gap: 8 }}>
              <button type="submit" className="btn btn-primary">Create</button>
              <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Inventory Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading inventory...</div>
      ) : inventories.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 60 }}>
          <Package size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
          <h3 style={{ color: 'var(--text-muted)' }}>No Inventory Points</h3>
          <p style={{ color: 'var(--text-muted)' }}>Create your first warehouse to start tracking supplies</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(450px, 1fr))', gap: 20 }}>
          {inventories.map(inv => (
            <div key={inv.id} className="card" style={{ position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 16 }}>
                <div>
                  <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{inv.name}</h3>
                  {inv.address && <div style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}><MapPin size={12} /> {inv.address}</div>}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>{inv.total_items} items</span>
                  {inv.low_stock_count > 0 && <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>{inv.low_stock_count} low</span>}
                </div>
              </div>

              {/* Items Table */}
              {inv.items.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <th style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>Item</th>
                        <th style={{ textAlign: 'center', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>Qty</th>
                        <th style={{ textAlign: 'center', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inv.items.map(item => (
                        <tr key={item.id} style={{ borderBottom: '1px solid var(--border-color)', background: item.is_low_stock ? 'rgba(239, 68, 68, 0.05)' : 'transparent' }}>
                          <td style={{ padding: '8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                            {item.is_low_stock && <AlertTriangle size={14} style={{ color: '#ef4444' }} />}
                            <div>
                              <div style={{ fontWeight: 500 }}>{item.item_name}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.category} · {item.unit}</div>
                            </div>
                          </td>
                          <td style={{ textAlign: 'center', fontWeight: 600, color: item.is_low_stock ? '#ef4444' : 'var(--text-primary)' }}>
                            {item.quantity}
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <button onClick={() => handleAdjust(item.id, -1)} style={{ background: 'rgba(239,68,68,0.1)', border: 'none', borderRadius: 4, cursor: 'pointer', color: '#ef4444', padding: '2px 8px', marginRight: 4 }}>-</button>
                            <button onClick={() => handleAdjust(item.id, 1)} style={{ background: 'rgba(5,150,105,0.1)', border: 'none', borderRadius: 4, cursor: 'pointer', color: '#059669', padding: '2px 8px' }}>+</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Add Item Form (inline) */}
              <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-color)' }}>
                <form onSubmit={(e) => { setSelectedInventory(inv.id); handleAddItem(e); }}
                  style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                  <select className="input" style={{ width: 100, padding: '4px 6px', fontSize: 12 }}
                    value={addItemForm.category} onChange={e => setAddItemForm({ ...addItemForm, category: e.target.value })}>
                    {['food', 'water', 'medical', 'shelter', 'clothing', 'rescue', 'sanitation', 'other'].map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <input className="input" style={{ flex: 1, minWidth: 100, padding: '4px 6px', fontSize: 12 }}
                    placeholder="Item name" value={addItemForm.item_name}
                    onChange={e => setAddItemForm({ ...addItemForm, item_name: e.target.value })} required />
                  <input className="input" type="number" style={{ width: 60, padding: '4px 6px', fontSize: 12 }}
                    value={addItemForm.quantity} onChange={e => setAddItemForm({ ...addItemForm, quantity: parseInt(e.target.value) || 0 })} />
                  <button type="submit" className="btn btn-primary" style={{ padding: '4px 10px', fontSize: 12 }}
                    onClick={() => setSelectedInventory(inv.id)}>
                    <Plus size={12} /> Add
                  </button>
                </form>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
