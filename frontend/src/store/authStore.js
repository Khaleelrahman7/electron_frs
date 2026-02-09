import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { API_BASE_URL } from '../utils/apiConfig';

const useAuthStore = create(
  persist(
    (set, get) => ({
      // State
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      login: async (username, password, role) => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password, role }),
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
            throw new Error(errorData.detail || 'Login failed');
          }

          const data = await response.json();
          
          set({
            user: {
              username: data.username,
              role: data.role,
              assigned_menus: data.assigned_menus,
            },
            token: data.access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          // Store token in localStorage for global fetch shim
          localStorage.setItem('auth_token', data.access_token);
          
          return { success: true };
        } catch (error) {
          set({
            isLoading: false,
            error: error.message,
          });
          return { success: false, error: error.message };
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          error: null,
        });
        localStorage.removeItem('auth_token');
      },

      clearError: () => {
        set({ error: null });
      },

      getCurrentUser: async () => {
        const { token } = get();
        if (!token) return null;

        try {
          const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });

          if (response.ok) {
            const userData = await response.json();
            set({ user: userData });
            return userData;
          } else {
            // Token is invalid, logout
            get().logout();
            return null;
          }
        } catch (error) {
          console.error('Error fetching current user:', error);
          return null;
        }
      },

      // Helper methods
      hasRole: (role) => {
        const { user } = get();
        return user?.role === role;
      },

      hasAnyRole: (roles) => {
        const { user } = get();
        return roles.includes(user?.role);
      },

      canManageUsers: () => {
        const { user } = get();
        return ['SuperAdmin', 'Admin'].includes(user?.role);
      },

      canManageCameras: () => {
        const { user } = get();
        return ['SuperAdmin', 'Admin'].includes(user?.role);
      },

      getAssignedCameras: () => {
        const { user } = get();
        return user?.assigned_cameras || [];
      },

      getAssignedMenus: () => {
        const { user } = get();
        return user?.assigned_menus || [];
      },

      hasMenuAccess: (menu) => {
        const { user } = get();
        const menus = (user?.assigned_menus || []).map(m => {
          if (m === 'cameras') return 'camera';
          if (m === 'admin') return 'users';
          return m;
        });
        return menus.includes(menu);
      },
    }),
    {
      name: 'auth-storage', // unique name for localStorage key
      partialize: (state) => ({ 
        user: state.user, 
        token: state.token, 
        isAuthenticated: state.isAuthenticated 
      }), // Only persist these fields
    }
  )
);

export default useAuthStore;
