import React, { useState, useEffect } from 'react';
import useAuthStore from '../../store/authStore';
import { API_BASE_URL } from '../../utils/apiConfig';
import { Users, UserPlus, Edit2, Trash2, X, Shield, Search } from 'lucide-react';
import './UserManagement.css';

const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    role: 'Admin',
    max_users_limit: 0,
    max_cameras_limit: 0,
    assigned_menus: []
  });

  const availableMenus = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'registration', label: 'Registration' },
    { id: 'gallery', label: 'Gallery' },
    { id: 'events', label: 'Events' },
    { id: 'matching', label: 'Face Matching' },
    { id: 'video', label: 'Video Processing' },
    { id: 'camera', label: 'Camera Management' },
    { id: 'stream-viewer', label: 'Stream Viewer' },
    { id: 'users', label: 'User Management' },
  ];

  const { user: currentUser, token } = useAuthStore();

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!response.ok) throw new Error('Failed to fetch users');
      
      const data = await response.json();
      setUsers(data.users);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name.includes('limit') ? parseInt(value) || 0 : value
    }));
  };

  const handleMenuChange = (menuId) => {
    setFormData(prev => {
      const currentMenus = prev.assigned_menus || [];
      if (currentMenus.includes(menuId)) {
        return { ...prev, assigned_menus: currentMenus.filter(id => id !== menuId) };
      } else {
        return { ...prev, assigned_menus: [...currentMenus, menuId] };
      }
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const endpoint = isEditing 
        ? `${API_BASE_URL}/api/users/${formData.username}`
        : `${API_BASE_URL}/api/users/`;
      
      const method = isEditing ? 'PUT' : 'POST';
      
      const body = { ...formData };
      if (isEditing) {
        // Only send updates if editing
        delete body.password; // Don't update password here for now
        delete body.username; // Can't change username
      }

      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Operation failed');
      }

      setShowModal(false);
      setFormData({
        username: '',
        password: '',
        role: 'Admin',
        max_users_limit: 0,
        max_cameras_limit: 0
      });
      setIsEditing(false);
      fetchUsers();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDelete = async (username) => {
    if (!window.confirm(`Are you sure you want to delete ${username}?`)) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/users/${username}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) throw new Error('Failed to delete user');
      
      fetchUsers();
    } catch (err) {
      alert(err.message);
    }
  };

  const openEditModal = (user) => {
    setFormData({
      username: user.username,
      password: '', // Password not required for edit
      role: user.role,
      max_users_limit: user.max_users_limit || 0,
      max_cameras_limit: user.max_cameras_limit || 0,
      assigned_menus: user.assigned_menus || []
    });
    setIsEditing(true);
    setShowModal(true);
  };

  const filteredUsers = users.filter(user => 
    user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.role.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) return <div className="loading">Loading users...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="user-management">
      <div className="header">
        <h2><Users size={24} /> User Management</h2>
        <div className="header-actions">
          <div className="search-bar">
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search users..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <button className="add-btn" onClick={() => {
            setIsEditing(false);
            setFormData({
              username: '',
              password: '',
              role: currentUser.role === 'SuperAdmin' ? 'Admin' : 'Supervisor',
              max_users_limit: 0,
              max_cameras_limit: 0,
              assigned_menus: ['dashboard'] // Default
            });
            setShowModal(true);
          }}>
            <UserPlus size={18} /> Add User
          </button>
        </div>
      </div>

      <div className="users-table-container">
        <table className="users-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th>Created By</th>
              {currentUser.role === 'SuperAdmin' && <th>Max Users</th>}
              <th>Max Cameras</th>
              <th>Assigned Cameras</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.map(user => (
              <tr key={user.username}>
                <td>{user.username}</td>
                <td>
                  <span className={`role-badge ${user.role.toLowerCase()}`}>
                    <Shield size={12} /> {user.role}
                  </span>
                </td>
                <td>{user.created_by || '-'}</td>
                {currentUser.role === 'SuperAdmin' && <td>{user.max_users_limit || 'Unlimited'}</td>}
                <td>{user.max_cameras_limit || 'Unlimited'}</td>
                <td>{user.assigned_cameras ? user.assigned_cameras.length : 0}</td>
                <td className="actions-cell">
                  <div className="actions-wrapper">
                    {user.role !== 'SuperAdmin' && (
                      <>
                        <button className="action-btn edit" onClick={() => openEditModal(user)} title="Edit">
                          <Edit2 size={16} />
                        </button>
                        <button className="action-btn delete" onClick={() => handleDelete(user.username)} title="Delete">
                          <Trash2 size={16} />
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>{isEditing ? 'Edit User' : 'Create New User'}</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              <div className="modal-content">
                {!isEditing && (
                  <>
                    <div className="form-group">
                      <label>Username</label>
                      <input
                        type="text"
                        name="username"
                        value={formData.username}
                        onChange={handleInputChange}
                        required
                        placeholder="Enter username"
                      />
                    </div>
                    <div className="form-group">
                      <label>Password</label>
                      <input
                        type="password"
                        name="password"
                        value={formData.password}
                        onChange={handleInputChange}
                        required
                        placeholder="Enter password"
                      />
                    </div>
                  </>
                )}
                
                <div className="form-group">
                  <label>Role</label>
                  <select name="role" value={formData.role} onChange={handleInputChange} disabled={isEditing}>
                    {currentUser.role === 'SuperAdmin' && <option value="Admin">Admin</option>}
                    <option value="Supervisor">Supervisor</option>
                  </select>
                </div>

                {/* License Controls - Only visible if creating Admin or if SuperAdmin is editing */}
                {(currentUser.role === 'SuperAdmin' && formData.role === 'Admin') && (
                  <>
                    <div className="form-group">
                      <label>Max Users License</label>
                      <input
                        type="number"
                        name="max_users_limit"
                        value={formData.max_users_limit}
                        onChange={handleInputChange}
                        min="0"
                      />
                      <small>Set to 0 for unlimited users</small>
                    </div>
                    <div className="form-group">
                      <label>Max Cameras License</label>
                      <input
                        type="number"
                        name="max_cameras_limit"
                        value={formData.max_cameras_limit}
                        onChange={handleInputChange}
                        min="0"
                      />
                      <small>Set to 0 for unlimited cameras</small>
                    </div>
                  </>
                )}

                {/* Menu Permissions */}
                <div className="form-group">
                  <label>Assigned Permissions (Sidebar)</label>
                  <div className="menu-checkboxes">
                    {availableMenus.map(menu => (
                      <div key={menu.id} className="checkbox-item">
                        <input
                          type="checkbox"
                          id={`menu-${menu.id}`}
                          checked={(formData.assigned_menus || []).includes(menu.id)}
                          onChange={() => handleMenuChange(menu.id)}
                        />
                        <label htmlFor={`menu-${menu.id}`}>{menu.label}</label>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="modal-actions">
                <button type="button" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="primary">{isEditing ? 'Update User' : 'Create User'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
