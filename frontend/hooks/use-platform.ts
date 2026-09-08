"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";

export function useExecutions(params: { page?: number; pageSize?: number; status?: string; mode?: string } = {}) {
  return useQuery({
    queryKey: ["executions", params],
    queryFn: async () => {
      const res = await apiClient.executions.list(params);
      return res.data;
    },
  });
}

export function useExecutionDetail(executionId: string) {
  return useQuery({
    queryKey: ["execution", executionId],
    queryFn: async () => {
      const res = await apiClient.executions.get(executionId);
      return res.data;
    },
    enabled: !!executionId,
  });
}

export function useApprovals() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: async () => {
      const res = await apiClient.approvals.listPending();
      return res.data || [];
    },
  });

  const resolveMutation = useMutation({
    mutationFn: async ({
      id,
      decision,
      comment,
    }: {
      id: string;
      decision: "APPROVED" | "REJECTED";
      comment?: string;
    }) => {
      return apiClient.approvals.resolve(id, decision, comment);
    },
    onSuccess: () => {
      // Invalidate pending approvals and related queries on decision
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["executions"] });
    },
  });

  return {
    ...query,
    resolve: resolveMutation.mutateAsync,
    isResolving: resolveMutation.isPending,
  };
}

export function useDatasets() {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: async () => {
      const res = await apiClient.datasets.list();
      return res.data || [];
    },
  });
}

export function useDatasetDetail(datasetId: string) {
  return useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: async () => {
      const res = await apiClient.datasets.get(datasetId);
      return res.data;
    },
    enabled: !!datasetId,
  });
}

export function useSemanticTerms() {
  return useQuery({
    queryKey: ["semantic", "terms"],
    queryFn: async () => {
      const res = await apiClient.semantic.getTerms();
      return res.data || [];
    },
  });
}

export function useSemanticMetrics() {
  return useQuery({
    queryKey: ["semantic", "metrics"],
    queryFn: async () => {
      const res = await apiClient.semantic.getMetrics();
      return res.data || [];
    },
  });
}

export function useEvaluationScorecards() {
  return useQuery({
    queryKey: ["evaluation", "scorecards"],
    queryFn: async () => {
      const res = await apiClient.evaluation.getScorecards();
      return res.data || [];
    },
  });
}
