"""In-memory adjacency graph algorithms: bounded BFS, path finding, and cycle detection."""

from collections import deque
from uuid import UUID

from app.knowledge_graph.domain.enums import GraphEdgeType
from app.knowledge_graph.domain.models import (
    GraphBudget,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphTraversal,
)


class AdjacencyEngine:
    """Provides deterministic bounded BFS graph traversal and path reasoning."""

    def __init__(self, budget: GraphBudget | None = None) -> None:
        self.budget = budget or GraphBudget()

    @staticmethod
    def build_adjacency(
        edges: list[GraphEdge],
    ) -> dict[UUID, list[tuple[UUID, GraphEdge]]]:
        """Build directed adjacency list from edges."""
        adj: dict[UUID, list[tuple[UUID, GraphEdge]]] = {}
        for edge in edges:
            adj.setdefault(edge.source_node_id, []).append((edge.target_node_id, edge))
        return adj

    @staticmethod
    def build_bidirectional_adjacency(
        edges: list[GraphEdge],
    ) -> dict[UUID, list[tuple[UUID, GraphEdge, bool]]]:
        """Build bidirectional adjacency list.

        Tuples are (neighbor_node_id, edge, is_outbound).
        """
        adj: dict[UUID, list[tuple[UUID, GraphEdge, bool]]] = {}
        for edge in edges:
            adj.setdefault(edge.source_node_id, []).append((edge.target_node_id, edge, True))
            adj.setdefault(edge.target_node_id, []).append((edge.source_node_id, edge, False))
        return adj

    def traverse(
        self,
        start_node_id: UUID,
        edges: list[GraphEdge],
        nodes_by_id: dict[UUID, GraphNode],
        max_depth: int | None = None,
        max_nodes: int | None = None,
        edge_types: list[GraphEdgeType] | None = None,
    ) -> GraphTraversal:
        """Bounded breadth-first traversal exploring neighbors up to max_depth."""
        depth_limit = min(max_depth or self.budget.max_depth, self.budget.max_depth)
        nodes_limit = min(max_nodes or self.budget.max_nodes, self.budget.max_nodes)
        edge_type_filter = {et.value for et in edge_types} if edge_types else None

        adj = self.build_bidirectional_adjacency(edges)
        visited_node_ids: set[UUID] = {start_node_id}
        visited_edges: list[GraphEdge] = []
        visited_nodes: list[GraphNode] = []

        if start_node_id in nodes_by_id:
            visited_nodes.append(nodes_by_id[start_node_id])

        # BFS queue elements: (current_node_id, current_depth)
        queue: deque[tuple[UUID, int]] = deque([(start_node_id, 0)])

        while queue:
            curr_id, curr_depth = queue.popleft()

            if curr_depth >= depth_limit:
                continue

            for neighbor_id, edge, _ in adj.get(curr_id, []):
                if edge_type_filter and edge.edge_type.value not in edge_type_filter:
                    continue

                if edge not in visited_edges:
                    visited_edges.append(edge)

                if neighbor_id not in visited_node_ids:
                    if len(visited_node_ids) >= nodes_limit:
                        # Controlled budget boundary enforcement
                        break

                    visited_node_ids.add(neighbor_id)
                    if neighbor_id in nodes_by_id:
                        visited_nodes.append(nodes_by_id[neighbor_id])

                    queue.append((neighbor_id, curr_depth + 1))

        return GraphTraversal(
            visited_nodes=visited_nodes,
            visited_edges=visited_edges,
            depth=depth_limit,
            paths=[],
        )

    def find_paths(
        self,
        start_node_id: UUID,
        target_node_id: UUID,
        edges: list[GraphEdge],
        nodes_by_id: dict[UUID, GraphNode],
        max_depth: int | None = None,
        max_paths: int | None = None,
        edge_types: list[GraphEdgeType] | None = None,
        only_verified: bool = False,
    ) -> list[GraphPath]:
        """Find deterministic bounded directed/undirected paths between two nodes using BFS."""
        depth_limit = min(max_depth or self.budget.max_depth, self.budget.max_depth)
        paths_limit = min(max_paths or self.budget.max_paths, self.budget.max_paths)
        edge_type_filter = {et.value for et in edge_types} if edge_types else None

        if only_verified:
            edges = [e for e in edges if e.is_verified]

        adj = self.build_bidirectional_adjacency(edges)

        # BFS state: (current_node_id, list of edge objects traversed, list of node_ids)
        queue: deque[tuple[UUID, list[GraphEdge], list[UUID]]] = deque(
            [(start_node_id, [], [start_node_id])]
        )

        discovered_paths: list[GraphPath] = []

        while queue and len(discovered_paths) < paths_limit:
            curr_id, path_edges, path_nodes = queue.popleft()

            if curr_id == target_node_id and len(path_edges) > 0:
                # Construct GraphPath
                nodes_in_path = [nodes_by_id[nid] for nid in path_nodes if nid in nodes_by_id]
                confidence = self._compute_path_confidence(path_edges)
                verified_count = sum(1 for e in path_edges if e.is_verified)
                verified_ratio = verified_count / len(path_edges) if path_edges else 0.0

                discovered_paths.append(
                    GraphPath(
                        nodes=nodes_in_path,
                        edges=path_edges,
                        depth=len(path_edges),
                        confidence=confidence,
                        verified_ratio=verified_ratio,
                    )
                )
                continue

            if len(path_edges) >= depth_limit:
                continue

            for neighbor_id, edge, _ in adj.get(curr_id, []):
                if edge_type_filter and edge.edge_type.value not in edge_type_filter:
                    continue

                if neighbor_id not in path_nodes:  # Avoid simple cycles
                    queue.append(
                        (
                            neighbor_id,
                            path_edges + [edge],
                            path_nodes + [neighbor_id],
                        )
                    )

        # Sort paths by confidence descending, then depth ascending
        discovered_paths.sort(key=lambda p: (-p.confidence, p.depth))
        return discovered_paths

    @staticmethod
    def detect_cycles(edges: list[GraphEdge]) -> list[list[UUID]]:
        """Identify cycle back-edges in directed graph using DFS coloring."""
        adj: dict[UUID, list[UUID]] = {}
        for edge in edges:
            adj.setdefault(edge.source_node_id, []).append(edge.target_node_id)

        # 0 = unvisited, 1 = visiting (on current stack), 2 = completely visited
        visited: dict[UUID, int] = {}
        parent_map: dict[UUID, UUID] = {}
        detected_cycles: list[list[UUID]] = []

        def dfs(node_id: UUID, current_path: list[UUID]) -> None:
            visited[node_id] = 1
            current_path.append(node_id)

            for neighbor_id in adj.get(node_id, []):
                if visited.get(neighbor_id, 0) == 1:
                    # Cycle detected: backtrack to neighbor
                    cycle_start_idx = current_path.index(neighbor_id)
                    detected_cycles.append(current_path[cycle_start_idx:] + [neighbor_id])
                elif visited.get(neighbor_id, 0) == 0:
                    parent_map[neighbor_id] = node_id
                    dfs(neighbor_id, current_path)

            current_path.pop()
            visited[node_id] = 2

        all_nodes = set(adj.keys())
        for node in all_nodes:
            if visited.get(node, 0) == 0:
                dfs(node, [])

        return detected_cycles

    @staticmethod
    def _compute_path_confidence(edges: list[GraphEdge]) -> float:
        """Compute path confidence bounded by the weakest link."""
        if not edges:
            return 0.0
        # Product of confidences with weakest-link constraint
        prod = 1.0
        min_conf = 1.0
        for e in edges:
            prod *= e.confidence
            if e.confidence < min_conf:
                min_conf = e.confidence
        # Bounded between [0.0, 1.0], never exceeding weakest link
        return round(min(prod, min_conf), 4)
