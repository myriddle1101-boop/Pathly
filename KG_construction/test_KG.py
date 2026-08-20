# 现在就可以运行的检查脚本
import networkx as nx

def check_kg_status(G):
    print("=" * 40)
    print("KG 状态检查报告")
    print("=" * 40)
    
    # 基本统计
    nodes = G.number_of_nodes()
    edges = G.number_of_edges()
    print(f"\n节点数：{nodes}")
    print(f"边数：{edges}")
    
    # 分类统计
    prereq = [(u,v) for u,v,d in G.edges(data=True) 
              if d.get('relation') == 'prerequisite']
    similar = [(u,v) for u,v,d in G.edges(data=True) 
               if d.get('relation') == 'similarity']
    print(f"先修关系：{len(prereq)} 条")
    print(f"相似关系：{len(similar)} 条")
    
    # 孤立节点
    isolated = list(nx.isolates(G))
    print(f"\n孤立节点：{len(isolated)} 个")
    if isolated:
        print(f"  → {isolated[:5]}")
    
    # 检查环
    try:
        cycle = nx.find_cycle(G)
        print(f"\n⚠️ 发现环：{cycle}")
    except nx.NetworkXNoCycle:
        print("\n✅ 无环（DAG结构正确）")
    
    # 连通性
    weakly_connected = nx.is_weakly_connected(G)
    print(f"\n弱连通：{weakly_connected}")
    
    # 功能性检查
    print("\n功能性检查：")
    test_pairs = [
        ("Python", "Transformer"),
        ("Linear Algebra", "Neural Networks"),
    ]
    for start, end in test_pairs:
        if start in G and end in G:
            has_path = nx.has_path(G, start, end)
            print(f"  {start} → {end}: "
                  f"{'✅' if has_path else '❌'}")
        else:
            print(f"  {start} 或 {end} 不在图中")
    
    print("\n" + "=" * 40)
    
    # 给出建议
    if nodes < 30:
        print("建议：节点数偏少，考虑增加输入文档")
    if len(isolated) > nodes * 0.1:
        print("建议：孤立节点过多，考虑降低相似度阈值")
    if weakly_connected:
        print("✅ 图结构良好，可以进行下一步")

check_kg_status(G)