"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { User } from "@/types/platform";
import { apiClient } from "@/lib/api/client";
import { useQueryClient } from "@tanstack/react-query";

const DEFAULT_USER: User = {
  id: "usr-demo-001",
  email: "analyst@enterprise.internal",
  full_name: "Principal Analyst",
  role: "ADMIN",
  organization_id: "00000000-0000-0000-0000-000000000001",
  organization_name: "Production Workspace",
  available_organizations: [
    { id: "00000000-0000-0000-0000-000000000001", name: "Production Workspace" },
    { id: "00000000-0000-0000-0000-000000000002", name: "Staging Financials" },
  ],
  permissions: [
    "analyst:query",
    "approvals:manage",
    "datasets:view",
    "semantic:publish",
    "evaluation:view",
    "models:manage",
  ],
};

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  activeOrgId: string | null;
  activeOrgName: string | null;
  canApprove: boolean;
  canPublish: boolean;
  canManageModels: boolean;
  canViewEvaluation: boolean;
  login: (username: string, password?: string) => Promise<void>;
  logout: () => Promise<void>;
  switchOrganization: (orgId: string, orgName: string) => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(DEFAULT_USER);
  const [isLoading, setIsLoading] = useState(false);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(DEFAULT_USER.organization_id);
  const [activeOrgName, setActiveOrgName] = useState<string | null>(DEFAULT_USER.organization_name || "Production Workspace");
  const queryClient = useQueryClient();

  useEffect(() => {
    let isMounted = true;
    apiClient.auth.me().then((res) => {
      if (isMounted && res.data) {
        setUser(res.data);
        setActiveOrgId(res.data.organization_id);
        setActiveOrgName(res.data.organization_name || "Enterprise Workspace");
      }
    }).catch(() => {
      // Keep initial default user
    });

    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (username: string, password?: string) => {
    setIsLoading(true);
    try {
      const res = await apiClient.auth.login({ username, password });
      if (res.data) {
        setUser(res.data);
        setActiveOrgId(res.data.organization_id);
        setActiveOrgName(res.data.organization_name || "Enterprise Workspace");
      }
      queryClient.invalidateQueries();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await apiClient.auth.logout();
    } catch {
      // ignore
    } finally {
      setUser(null);
      setActiveOrgId(null);
      queryClient.clear();
    }
  };

  const switchOrganization = (orgId: string, orgName: string) => {
    setActiveOrgId(orgId);
    setActiveOrgName(orgName);
    // Invalidate all server queries and reset execution context on tenant switch
    queryClient.invalidateQueries();
  };

  const refreshUser = async () => {
    try {
      const res = await apiClient.auth.me();
      if (res.data) {
        setUser(res.data);
        setActiveOrgId(res.data.organization_id);
        setActiveOrgName(res.data.organization_name || "Enterprise Workspace");
      }
    } catch {
      // ignore
    }
  };

  const permissions = user?.permissions || [];
  const canApprove = permissions.includes("approvals:manage") || user?.role === "ADMIN";
  const canPublish = permissions.includes("semantic:publish") || user?.role === "ADMIN";
  const canManageModels = permissions.includes("models:manage") || user?.role === "ADMIN";
  const canViewEvaluation = permissions.includes("evaluation:view") || user?.role === "ADMIN";

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        activeOrgId,
        activeOrgName,
        canApprove,
        canPublish,
        canManageModels,
        canViewEvaluation,
        login,
        logout,
        switchOrganization,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
