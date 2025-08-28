#!/usr/bin/env python3
"""
Dependency graph visualization for Poetry projects.
Creates interactive visualizations of package dependencies.
"""

import logging
import subprocess
from pathlib import Path

import click
import networkx as nx
import toml
from pyvis.network import Network

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DependencyVisualizer:
    """Create dependency graph visualizations."""
    
    def __init__(self, project_root: Path | None = None):
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = project_root
        self.pyproject_path = project_root / "pyproject.toml"
        self.output_dir = project_root / "dependency_reports" / "graphs"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Node categories and colors
        self.node_colors = {
            "main": "#4CAF50",      # Green for main deps
            "dev": "#2196F3",       # Blue for dev deps
            "ml": "#FF9800",        # Orange for ML deps
            "optional": "#9C27B0",  # Purple for optional
            "transitive": "#757575", # Gray for transitive
            "external": "#F44336",   # Red for external
        }
        
        self.node_sizes = {
            "main": 30,
            "dev": 25,
            "ml": 35,
            "optional": 20,
            "transitive": 15,
            "external": 15,
        }
    
    def parse_poetry_lock(self) -> dict:
        """Parse poetry.lock file for dependency information."""
        lock_file = self.project_root / "poetry.lock"
        
        if not lock_file.exists():
            logger.warning("poetry.lock not found, generating...")
            subprocess.run(["python3", "-m", "poetry", "lock"], check=True)
        
        with open(lock_file) as f:
            lock_data = toml.load(f)
        
        return lock_data
    
    def build_dependency_graph(self) -> nx.DiGraph:
        """Build networkx graph from dependencies."""
        G = nx.DiGraph()
        
        # Parse pyproject.toml
        with open(self.pyproject_path) as f:
            pyproject = toml.load(f)
        
        poetry_config = pyproject.get("tool", {}).get("poetry", {})
        
        # Add main dependencies
        main_deps = poetry_config.get("dependencies", {})
        for dep, _spec in main_deps.items():
            if dep != "python":
                G.add_node(dep, category="main", level=1)
        
        # Add dev dependencies
        dev_group = poetry_config.get("group", {}).get("dev", {}).get("dependencies", {})
        for dep, _spec in dev_group.items():
            G.add_node(dep, category="dev", level=1)
        
        # Add ML dependencies
        ml_cpu_group = poetry_config.get("group", {}).get("ml-cpu", {}).get("dependencies", {})
        for dep, _spec in ml_cpu_group.items():
            G.add_node(dep, category="ml", level=1)
        
        ml_gpu_group = poetry_config.get("group", {}).get("ml-gpu", {}).get("dependencies", {})
        for dep, _spec in ml_gpu_group.items():
            G.add_node(dep, category="ml", level=1)
        
        # Parse lock file for transitive dependencies
        try:
            lock_data = self.parse_poetry_lock()
            packages = lock_data.get("package", [])
            
            for package in packages:
                name = package["name"]
                deps = package.get("dependencies", {})
                
                # Add node if not exists
                if name not in G:
                    G.add_node(name, category="transitive", level=2)
                
                # Add edges for dependencies
                for dep_name, dep_spec in deps.items():
                    # Handle complex dependency specs
                    if isinstance(dep_spec, dict):
                        dep_name = dep_name
                    
                    if dep_name not in G:
                        G.add_node(dep_name, category="transitive", level=3)
                    
                    G.add_edge(name, dep_name)
        
        except Exception as e:
            logger.warning(f"Could not parse lock file: {e}")
        
        return G
    
    def create_interactive_graph(self, G: nx.DiGraph, output_file: str = "dependency_graph.html"):
        """Create interactive HTML visualization."""
        net = Network(height="800px", width="100%", directed=True, notebook=False)
        net.barnes_hut(gravity=-80000, central_gravity=0.3, spring_length=250)
        
        # Add nodes
        for node in G.nodes():
            node_data = G.nodes[node]
            category = node_data.get("category", "external")
            
            net.add_node(
                node,
                label=node,
                color=self.node_colors.get(category, "#757575"),
                size=self.node_sizes.get(category, 15),
                title=f"{node}\nCategory: {category}",
                level=node_data.get("level", 4)
            )
        
        # Add edges
        for source, target in G.edges():
            net.add_edge(source, target, arrows="to")
        
        # Configure physics
        net.set_options("""
        {
            "physics": {
                "enabled": true,
                "solver": "hierarchicalRepulsion",
                "hierarchicalRepulsion": {
                    "nodeDistance": 120,
                    "springLength": 100,
                    "springConstant": 0.01
                }
            },
            "layout": {
                "hierarchical": {
                    "enabled": true,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "nodeSpacing": 200,
                    "levelSeparation": 150
                }
            },
            "interaction": {
                "hover": true,
                "navigationButtons": true,
                "keyboard": true
            }
        }
        """)
        
        # Save graph
        output_path = self.output_dir / output_file
        net.save_graph(str(output_path))
        
        return output_path
    
    def analyze_graph_metrics(self, G: nx.DiGraph) -> dict:
        """Analyze graph metrics for insights."""
        metrics = {}
        
        # Basic metrics
        metrics["total_packages"] = G.number_of_nodes()
        metrics["total_dependencies"] = G.number_of_edges()
        metrics["density"] = nx.density(G)
        
        # Find most connected packages
        in_degree = dict(G.in_degree())
        out_degree = dict(G.out_degree())
        
        metrics["most_depended_on"] = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:10]
        metrics["most_dependencies"] = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Find circular dependencies
        try:
            cycles = list(nx.simple_cycles(G))
            metrics["circular_dependencies"] = len(cycles)
            metrics["circular_deps_list"] = cycles[:5] if cycles else []
        except (nx.NetworkXError, RecursionError):
            metrics["circular_dependencies"] = 0
            metrics["circular_deps_list"] = []
        
        # Calculate depth
        if G.number_of_nodes() > 0:
            try:
                # Find root nodes (no incoming edges)
                roots = [n for n in G.nodes() if G.in_degree(n) == 0]
                if roots:
                    max_depth = 0
                    for root in roots:
                        lengths = nx.single_source_shortest_path_length(G, root)
                        max_depth = max(max_depth, max(lengths.values()))
                    metrics["max_depth"] = max_depth
                else:
                    metrics["max_depth"] = 0
            except (nx.NetworkXError, KeyError, ValueError):
                metrics["max_depth"] = 0
        
        # Identify potential issues
        metrics["potential_issues"] = []
        
        # Check for too many dependencies
        for node, degree in out_degree.items():
            if degree > 10:
                metrics["potential_issues"].append(f"{node} has {degree} direct dependencies")
        
        # Check for single points of failure
        for node, degree in in_degree.items():
            if degree > 20:
                metrics["potential_issues"].append(f"{node} is depended on by {degree} packages")
        
        return metrics
    
    def generate_dependency_report(self, G: nx.DiGraph) -> str:
        """Generate text report of dependencies."""
        metrics = self.analyze_graph_metrics(G)
        
        report = []
        report.append("# Dependency Analysis Report")
        report.append("")
        report.append("## Summary")
        report.append(f"- Total Packages: {metrics['total_packages']}")
        report.append(f"- Total Dependencies: {metrics['total_dependencies']}")
        report.append(f"- Graph Density: {metrics['density']:.3f}")
        report.append(f"- Max Dependency Depth: {metrics.get('max_depth', 'N/A')}")
        report.append(f"- Circular Dependencies: {metrics['circular_dependencies']}")
        report.append("")
        
        report.append("## Most Depended On Packages")
        for pkg, count in metrics["most_depended_on"][:5]:
            report.append(f"- {pkg}: {count} packages depend on this")
        report.append("")
        
        report.append("## Packages with Most Dependencies")
        for pkg, count in metrics["most_dependencies"][:5]:
            report.append(f"- {pkg}: depends on {count} packages")
        report.append("")
        
        if metrics["circular_deps_list"]:
            report.append("## Circular Dependencies Detected")
            for cycle in metrics["circular_deps_list"]:
                report.append(f"- {' -> '.join(cycle)} -> {cycle[0]}")
            report.append("")
        
        if metrics["potential_issues"]:
            report.append("## Potential Issues")
            for issue in metrics["potential_issues"]:
                report.append(f"- ⚠️ {issue}")
            report.append("")
        
        # Add category breakdown
        categories = {}
        for node in G.nodes():
            cat = G.nodes[node].get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        
        report.append("## Package Categories")
        for cat, count in sorted(categories.items()):
            report.append(f"- {cat}: {count} packages")
        
        return "\n".join(report)
    
    def export_to_dot(self, G: nx.DiGraph, output_file: str = "dependency_graph.dot"):
        """Export graph to Graphviz DOT format."""
        output_path = self.output_dir / output_file
        
        # Create DOT content
        dot_lines = ["digraph dependencies {"]
        dot_lines.append('  rankdir=TB;')
        dot_lines.append('  node [shape=box, style=rounded];')
        
        # Add nodes with styling
        for node in G.nodes():
            node_data = G.nodes[node]
            category = node_data.get("category", "external")
            color = self.node_colors.get(category, "#757575")
            dot_lines.append(f'  "{node}" [fillcolor="{color}", style=filled];')
        
        # Add edges
        for source, target in G.edges():
            dot_lines.append(f'  "{source}" -> "{target}";')
        
        dot_lines.append("}")
        
        with open(output_path, 'w') as f:
            f.write("\n".join(dot_lines))
        
        return output_path
    
    def create_simplified_graph(self, G: nx.DiGraph, max_nodes: int = 50) -> nx.DiGraph:
        """Create simplified graph showing only main dependencies."""
        # Get most important nodes based on degree
        node_importance = {}
        for node in G.nodes():
            in_deg = G.in_degree(node)
            out_deg = G.out_degree(node)
            category = G.nodes[node].get("category", "external")
            
            # Weight by category importance
            weight = 1.0
            if category == "main":
                weight = 3.0
            elif category == "dev":
                weight = 2.0
            elif category == "ml":
                weight = 2.5
            
            node_importance[node] = (in_deg + out_deg) * weight
        
        # Select top nodes
        important_nodes = sorted(node_importance.items(), key=lambda x: x[1], reverse=True)
        selected_nodes = [node for node, _ in important_nodes[:max_nodes]]
        
        # Create subgraph
        H = G.subgraph(selected_nodes).copy()
        
        return H


@click.group()
def cli():
    """Dependency visualization for Poetry projects."""
    pass


@cli.command()
@click.option('--output', default='dependency_graph.html', help='Output filename')
@click.option('--simplified', is_flag=True, help='Create simplified graph')
@click.option('--max-nodes', default=50, help='Max nodes for simplified graph')
def visualize(output: str, simplified: bool, max_nodes: int):
    """Create interactive dependency graph."""
    visualizer = DependencyVisualizer()
    
    logger.info("Building dependency graph...")
    G = visualizer.build_dependency_graph()
    
    if simplified:
        logger.info(f"Creating simplified graph (max {max_nodes} nodes)...")
        G = visualizer.create_simplified_graph(G, max_nodes)
    
    logger.info("Creating interactive visualization...")
    output_path = visualizer.create_interactive_graph(G, output)
    
    logger.info(f"✅ Graph saved to {output_path}")
    logger.info(f"Open {output_path} in a web browser to view")


@cli.command()
def analyze():
    """Analyze dependency graph metrics."""
    visualizer = DependencyVisualizer()
    
    logger.info("Building dependency graph...")
    G = visualizer.build_dependency_graph()
    
    logger.info("Generating analysis report...")
    report = visualizer.generate_dependency_report(G)
    
    print("\n" + report)
    
    # Save report
    report_file = visualizer.output_dir / "dependency_analysis.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    logger.info(f"\n✅ Report saved to {report_file}")


@cli.command()
@click.option('--output', default='dependency_graph.dot', help='Output filename')
def export_dot(output: str):
    """Export dependency graph to DOT format."""
    visualizer = DependencyVisualizer()
    
    logger.info("Building dependency graph...")
    G = visualizer.build_dependency_graph()
    
    logger.info("Exporting to DOT format...")
    output_path = visualizer.export_to_dot(G, output)
    
    logger.info(f"✅ DOT file saved to {output_path}")
    logger.info("To generate image: dot -Tpng dependency_graph.dot -o dependency_graph.png")


@cli.command()
def check_cycles():
    """Check for circular dependencies."""
    visualizer = DependencyVisualizer()
    
    logger.info("Building dependency graph...")
    G = visualizer.build_dependency_graph()
    
    try:
        cycles = list(nx.simple_cycles(G))
        
        if cycles:
            logger.warning(f"⚠️ Found {len(cycles)} circular dependencies:")
            for i, cycle in enumerate(cycles, 1):
                print(f"{i}. {' -> '.join(cycle)} -> {cycle[0]}")
        else:
            logger.info("✅ No circular dependencies found!")
    
    except Exception as e:
        logger.error(f"Error checking cycles: {e}")


if __name__ == "__main__":
    cli()