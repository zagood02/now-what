"use client";

import { useAuth } from '@/app/contexts/AuthContext';

export default function AuthButton() {
  const { user, login, logout } = useAuth();

  const handleLogin = () => {
    // 임시 로그인 로직
    login({ id: 1, name: 'Test User', email: 'test@example.com' });
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <div>
      {user ? (
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">{user.name}</span>
          <button
            onClick={handleLogout}
            className="px-3 py-1 bg-red-500 text-white rounded text-sm hover:bg-red-600"
          >
            로그아웃
          </button>
        </div>
      ) : (
        <button
          onClick={handleLogin}
          className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
        >
          로그인
        </button>
      )}
    </div>
  );
}