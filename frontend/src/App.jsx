import React, { useEffect, useMemo, useRef, useState } from 'react';
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from 'd3-force';

const FRONTEND_VERSION = 'v0.1.4-内测';
const emptyOutput = { format: '', content: '', filePath: '' };
const GRAPH_WIDTH = 800;
const GRAPH_HEIGHT = 420;

const formatScore = (value) => {
  if (value === null || value === undefined) return '-';
  return `${Math.round(value * 100)}%`;
};

export default function App() {
  const [tboxFile, setTboxFile] = useState(null);
  const [tboxAllProps, setTboxAllProps] = useState([]);
  const [tboxClasses, setTboxClasses] = useState([]);
  const [tboxObjectProps, setTboxObjectProps] = useState([]);
  const [tboxTtl, setTboxTtl] = useState('');
  const [tboxView, setTboxView] = useState('graph');
  const [leafOnly, setLeafOnly] = useState(false);
  const [dataFiles, setDataFiles] = useState([]);
  const [directoryMode, setDirectoryMode] = useState(false);
  const [tables, setTables] = useState([]);
  const [fileCount, setFileCount] = useState(0);
  const [tableCount, setTableCount] = useState(0);
  const [previewTable, setPreviewTable] = useState('');
  const [matches, setMatches] = useState([]);
  const [matchMode, setMatchMode] = useState('llm');
  const [confidence, setConfidence] = useState(50);
  const [output, setOutput] = useState(emptyOutput);
  const [status, setStatus] = useState('');
  const [sourceType, setSourceType] = useState('file');
  const [jdbcInfo, setJdbcInfo] = useState({ url: '', user: '', password: '' });
  const [tableName, setTableName] = useState('data_table');
  const [backendVersion, setBackendVersion] = useState('未连接');
  const [busy, setBusy] = useState(false);
  const [graphNodes, setGraphNodes] = useState([]);
  const [graphLinks, setGraphLinks] = useState([]);
  const [draggingId, setDraggingId] = useState(null);
  const simulationRef = useRef(null);
  const nodesRef = useRef([]);
  const svgRef = useRef(null);

  const fieldCount = useMemo(() => {
    const set = new Set();
    tables.forEach((table) => {
      (table.fields || []).forEach((field) => set.add(field));
    });
    return set.size;
  }, [tables]);

  const leafCount = useMemo(() => {
    return tboxAllProps.filter((prop) => prop.is_leaf).length;
  }, [tboxAllProps]);

  const tboxProps = useMemo(() => {
    if (!leafOnly) return tboxAllProps;
    return tboxAllProps.filter((prop) => prop.is_leaf);
  }, [tboxAllProps, leafOnly]);

  const groupedProps = useMemo(() => {
    const groups = new Map();
    tboxProps.forEach((prop) => {
      const domain = prop.domains && prop.domains.length ? prop.domains[0] : null;
      const className = domain?.label || domain?.local_name || domain?.iri || '未指定类';
      const classKey = domain?.iri || className;
      if (!groups.has(classKey)) {
        groups.set(classKey, { className, classIri: domain?.iri || '', properties: [] });
      }
      groups.get(classKey).properties.push(prop);
    });
    return Array.from(groups.values());
  }, [tboxProps]);

  const groupedMatches = useMemo(() => {
    const matchMap = new Map(matches.map((item) => [item.property_iri, item]));
    return groupedProps.map((group) => ({
      ...group,
      items: group.properties.map((prop) => {
        const match = matchMap.get(prop.iri);
        return {
          property_iri: prop.iri,
          property_label: prop.label || prop.local_name,
          table_name: match?.table_name || '',
          field: match?.field || '',
          score: match?.score ?? null
        };
      })
    }));
  }, [groupedProps, matches]);

  useEffect(() => {
    const { nodes, links } = buildGraphData(tboxClasses, tboxObjectProps);
    setGraphLinks(links);
    setGraphNodes(nodes);
    nodesRef.current = nodes;

    if (!nodes.length) {
      if (simulationRef.current) {
        simulationRef.current.stop();
      }
      return undefined;
    }

    if (simulationRef.current) {
      simulationRef.current.stop();
    }

    const simulation = forceSimulation(nodes)
      .force('charge', forceManyBody().strength(-240))
      .force('center', forceCenter(GRAPH_WIDTH / 2, GRAPH_HEIGHT / 2))
      .force('link', forceLink(links).id((node) => node.id).distance(120))
      .force('collide', forceCollide(28));

    simulation.on('tick', () => {
      setGraphNodes([...nodes]);
    });

    simulationRef.current = simulation;
    return () => simulation.stop();
  }, [tboxClasses, tboxObjectProps]);

  const mappingPayload = useMemo(() => {
    return matches
      .filter((item) => item.table_name && item.field)
      .map((item) => ({
        table_name: item.table_name,
        field: item.field,
        property_iri: item.property_iri
      }));
  }, [matches]);

  const fileListLabel = useMemo(() => {
    if (!dataFiles.length) return '未选择文件';
    const names = dataFiles
      .slice(0, 3)
      .map((file) => file.webkitRelativePath || file.name)
      .join('、');
    return dataFiles.length > 3 ? `${names} 等 ${dataFiles.length} 个文件` : names;
  }, [dataFiles]);

  const previewTableInfo = useMemo(() => {
    return tables.find((table) => table.name === previewTable) || null;
  }, [tables, previewTable]);

  useEffect(() => {
    if (!previewTable && tables.length) {
      setPreviewTable(tables[0].name);
    }
  }, [tables, previewTable]);

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const response = await fetch('/api/version');
        if (!response.ok) throw new Error('版本获取失败');
        const data = await response.json();
        setBackendVersion(data.version || '未知');
      } catch (error) {
        setBackendVersion('未连接');
      }
    };
    fetchVersion();
  }, []);

  useEffect(() => {
    if (!tboxProps.length) {
      setMatches([]);
      return;
    }
    setMatches(
      tboxProps.map((prop) => ({
        property_iri: prop.iri,
        property_label: prop.label || prop.local_name,
        table_name: '',
        field: '',
        score: null
      }))
    );
  }, [tboxProps]);

  const handleStatus = (message) => {
    setStatus(message);
    if (!message) return;
    setTimeout(() => setStatus(''), 4000);
  };

  const parseTbox = async () => {
    if (!tboxFile) {
      handleStatus('请选择 TBox 文件');
      return;
    }
    setBusy(true);
    try {
      const formData = new FormData();
      formData.append('file', tboxFile);
      const response = await fetch('/api/tbox/parse', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'TBox 解析失败');
      setTboxAllProps(data.properties || []);
      setTboxClasses(data.classes || []);
      setTboxObjectProps(data.object_properties || []);
      setTboxTtl(data.ttl || '');
      setTboxView('graph');
      handleStatus(`已解析 TBox：${data.properties?.length || 0} 个数据属性`);
    } catch (error) {
      handleStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const parseDataSource = async () => {
    if (sourceType === 'jdbc') {
      handleStatus('JDBC Demo 暂未启用，请使用 CSV/XLSX');
      return;
    }
    if (!dataFiles.length) {
      handleStatus('请选择 CSV/XLSX 文件或目录');
      return;
    }
    setBusy(true);
    try {
      const formData = new FormData();
      dataFiles.forEach((file) => formData.append('files', file));
      const response = await fetch('/api/data/parse', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '数据解析失败');
      const nextTables = data.tables || [];
      const nextTableCount = data.table_count || nextTables.length;
      const nextFieldCount = new Set(
        nextTables.flatMap((table) => table.fields || [])
      ).size;
      setTables(nextTables);
      setFileCount(data.file_count || dataFiles.length);
      setTableCount(nextTableCount);
      setMatches((prev) =>
        prev.map((item) => ({ ...item, table_name: '', field: '', score: null }))
      );
      handleStatus(`已解析表：${nextTableCount}，字段数：${nextFieldCount}`);
    } catch (error) {
      handleStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const runMatch = async () => {
    if (!tables.length || !tboxProps.length) {
      handleStatus('请先完成 TBox 与数据解析');
      return;
    }
    setBusy(true);
    try {
      const response = await fetch('/api/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          properties: tboxProps,
          tables,
          mode: matchMode,
          threshold: confidence / 100
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '匹配失败');
      setMatches(data.matches || []);
      handleStatus('已生成自动匹配结果');
    } catch (error) {
      handleStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const updateTableSelection = (propertyIri, tableNameValue) => {
    setMatches((prev) =>
      prev.map((item) => {
        if (item.property_iri !== propertyIri) return item;
        return { ...item, table_name: tableNameValue, field: '' };
      })
    );
  };

  const updateFieldSelection = (propertyIri, fieldValue) => {
    setMatches((prev) =>
      prev.map((item) =>
        item.property_iri === propertyIri ? { ...item, field: fieldValue } : item
      )
    );
  };

  const generateAbox = async () => {
    if (!mappingPayload.length || !tables.length) {
      handleStatus('请先完成匹配并确保有数据');
      return;
    }
    setBusy(true);
    try {
      const response = await fetch('/api/abox', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tables, mapping: mappingPayload })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'ABox 生成失败');
      setOutput({ format: data.format, content: data.content, filePath: data.file_path || '' });
      handleStatus('ABox 生成完成');
    } catch (error) {
      handleStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const generateR2Rml = async () => {
    if (!mappingPayload.length) {
      handleStatus('请先完成匹配');
      return;
    }
    setBusy(true);
    try {
      const response = await fetch('/api/r2rml', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mapping: mappingPayload, table_name: tableName })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'R2RML 生成失败');
      setOutput({ format: data.format, content: data.content, filePath: '' });
      handleStatus('R2RML 生成完成');
    } catch (error) {
      handleStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const resetAll = () => {
    setTboxFile(null);
    setTboxAllProps([]);
    setTboxClasses([]);
    setTboxObjectProps([]);
    setTboxTtl('');
    setTboxView('graph');
    setDataFiles([]);
    setTables([]);
    setFileCount(0);
    setTableCount(0);
    setMatches([]);
    setOutput(emptyOutput);
    setStatus('');
  };

  const handlePointerDown = (node, event) => {
    event.preventDefault();
    setDraggingId(node.id);
    node.fx = node.x;
    node.fy = node.y;
    if (simulationRef.current) {
      simulationRef.current.alphaTarget(0.2).restart();
    }
  };

  const handlePointerMove = (event) => {
    if (!draggingId || !svgRef.current) return;
    const node = nodesRef.current.find((item) => item.id === draggingId);
    if (!node) return;
    const point = getSvgPoint(svgRef.current, event, GRAPH_WIDTH, GRAPH_HEIGHT);
    node.fx = point.x;
    node.fy = point.y;
    setGraphNodes([...nodesRef.current]);
  };

  const handlePointerUp = () => {
    if (!draggingId) return;
    const node = nodesRef.current.find((item) => item.id === draggingId);
    if (node) {
      node.fx = null;
      node.fy = null;
    }
    setDraggingId(null);
    if (simulationRef.current) {
      simulationRef.current.alphaTarget(0);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">R2RML 演示</p>
          <h1>语义映射工作台</h1>
          <p className="subtitle">
            将业务字段与 TBox 数据属性对齐，生成 ABox 或 R2RML 映射。
          </p>
        </div>
        <div className="hero-actions">
          <button className="ghost" onClick={resetAll} disabled={busy}>
            重置流程
          </button>
          <span className={`status ${status ? 'show' : ''}`}>{status}</span>
        </div>
      </header>

      <section className="grid">
        <article className="card">
          <div className="card-head">
            <h2>1. 上传 TBox</h2>
            <span className="tag">RDF / OWL</span>
          </div>
          <p className="hint">解析本体数据属性，为后续匹配提供语义锚点。</p>
          <div className="field">
            <input
              type="file"
              accept=".rdf,.owl,.ttl,.xml"
              onChange={(event) => setTboxFile(event.target.files?.[0] || null)}
            />
            <button onClick={parseTbox} disabled={busy}>
              解析 TBox
            </button>
          </div>
          <div className="summary">
            <span>已识别属性</span>
            <strong>{tboxProps.length}</strong>
          </div>
          <div className="filter-row">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={leafOnly}
                onChange={(event) => setLeafOnly(event.target.checked)}
              />
              只显示叶子属性（{leafCount} / {tboxAllProps.length}）
            </label>
          </div>
          <div className="list">
            {groupedProps.map((group) => (
              <div key={group.classIri || group.className} className="class-group">
                <div className="class-title">
                  <span className="mono">{group.className}</span>
                  {group.classIri ? <small>{group.classIri}</small> : null}
                </div>
                <div className="class-items">
                  {group.properties.slice(0, 6).map((prop) => (
                    <div key={prop.iri} className="class-item">
                      <span>{prop.label || prop.local_name}</span>
                    </div>
                  ))}
                  {group.properties.length > 6 && (
                    <small>还有 {group.properties.length - 6} 个属性未展示</small>
                  )}
                </div>
              </div>
            ))}
            {!groupedProps.length && <small>等待上传解析</small>}
          </div>
        </article>

        <article className="card wide tbox-pane">
          <div className="card-head">
            <h2>1.5 TBox 视图</h2>
            <div className="tab-toggle">
              <button
                className={tboxView === 'graph' ? 'active' : ''}
                onClick={() => setTboxView('graph')}
              >
                GRAPH
              </button>
              <button
                className={tboxView === 'ttl' ? 'active' : ''}
                onClick={() => setTboxView('ttl')}
              >
                TBOX TTL
              </button>
            </div>
          </div>
          <div className="pane-body">
            {tboxView === 'graph' ? (
              <div className="graph-wrapper">
                {graphNodes.length ? (
                  <svg
                    ref={svgRef}
                    className="graph-canvas"
                    viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
                    onPointerMove={handlePointerMove}
                    onPointerUp={handlePointerUp}
                    onPointerLeave={handlePointerUp}
                  >
                    <defs>
                      <marker
                        id="arrow"
                        markerWidth="8"
                        markerHeight="8"
                        refX="12"
                        refY="4"
                        orient="auto"
                      >
                        <path d="M0,0 L8,4 L0,8 Z" fill="#1f3a5f" />
                      </marker>
                    </defs>
                    {graphLinks.map((link) => (
                      <g key={link.id}>
                        <line
                          x1={link.source.x}
                          y1={link.source.y}
                          x2={link.target.x}
                          y2={link.target.y}
                          stroke="#1f3a5f"
                          strokeWidth="1.2"
                          markerEnd="url(#arrow)"
                          opacity="0.6"
                        />
                        <text
                          x={(link.source.x + link.target.x) / 2}
                          y={(link.source.y + link.target.y) / 2}
                          className="edge-label"
                        >
                          {link.label}
                        </text>
                      </g>
                    ))}
                    {graphNodes.map((node) => (
                      <g
                        key={node.id}
                        transform={`translate(${node.x}, ${node.y})`}
                        onPointerDown={(event) => handlePointerDown(node, event)}
                      >
                        <circle r="18" fill="#ffffff" stroke="#1f3a5f" strokeWidth="1.5" />
                        <text textAnchor="middle" className="node-label" y="4">
                          {node.label}
                        </text>
                      </g>
                    ))}
                  </svg>
                ) : (
                  <small>解析 TBox 后可展示图谱。</small>
                )}
              </div>
            ) : (
              <pre className="ttl-viewer">{tboxTtl || '暂无 TBox TTL 输出。'}</pre>
            )}
          </div>
        </article>

        <article className="card">
          <div className="card-head">
            <h2>2. 数据源</h2>
            <span className="tag">CSV / XLSX</span>
          </div>
          <div className="toggle">
            <button
              className={sourceType === 'file' ? 'active' : ''}
              onClick={() => setSourceType('file')}
            >
              文件上传
            </button>
            <button
              className={sourceType === 'jdbc' ? 'active' : ''}
              onClick={() => setSourceType('jdbc')}
            >
              JDBC 连接
            </button>
          </div>

          {sourceType === 'file' ? (
            <div className="file-block">
              <div className="field">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  multiple
                  {...(directoryMode ? { webkitdirectory: 'true', directory: 'true' } : {})}
                  key={directoryMode ? 'directory' : 'files'}
                  onChange={(event) => setDataFiles(Array.from(event.target.files || []))}
                />
                <button onClick={parseDataSource} disabled={busy}>
                  解析字段
                </button>
              </div>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={directoryMode}
                  onChange={(event) => {
                    setDirectoryMode(event.target.checked);
                    setDataFiles([]);
                  }}
                />
                目录上传（读取目录内所有 CSV/XLSX）
              </label>
              <div className="file-list">
                <span className="mono">{fileListLabel}</span>
              </div>
            </div>
          ) : (
            <div className="jdbc">
              <input
                type="text"
                placeholder="jdbc:postgresql://host:5432/db"
                value={jdbcInfo.url}
                onChange={(event) => setJdbcInfo({ ...jdbcInfo, url: event.target.value })}
                disabled
              />
              <div className="jdbc-row">
                <input
                  type="text"
                  placeholder="user"
                  value={jdbcInfo.user}
                  onChange={(event) => setJdbcInfo({ ...jdbcInfo, user: event.target.value })}
                  disabled
                />
                <input
                  type="password"
                  placeholder="password"
                  value={jdbcInfo.password}
                  onChange={(event) => setJdbcInfo({ ...jdbcInfo, password: event.target.value })}
                  disabled
                />
              </div>
              <small>JDBC Demo 暂未启用，后续可接入。</small>
            </div>
          )}

          <div className="summary">
            <span>表数量</span>
            <strong>{tableCount}</strong>
          </div>
          <div className="summary">
            <span>字段数量</span>
            <strong>{fieldCount}</strong>
          </div>
          <div className="summary">
            <span>文件数量</span>
            <strong>{fileCount}</strong>
          </div>

          <div className="list">
            {tables.slice(0, 4).map((table) => (
              <div key={table.name}>
                <p className="mono">{table.name}</p>
                <small>{(table.fields || []).length} 个字段</small>
              </div>
            ))}
            {!tables.length && <small>等待数据源解析</small>}
          </div>
        </article>

        <article className="card wide">
          <div className="card-head">
            <h2>3. 自动匹配与调整</h2>
            <span className="tag">语义匹配</span>
          </div>
          <div className="actions">
            <div className="mode">
              <label>
                匹配模式
                <select value={matchMode} onChange={(event) => setMatchMode(event.target.value)}>
                  <option value="heuristic">启发式</option>
                  <option value="llm">LLM（Qwen）</option>
                </select>
              </label>
            </div>
            <div className="slider">
              <label>
                置信度阈值：{confidence}%
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={confidence}
                  onChange={(event) => setConfidence(Number(event.target.value))}
                />
              </label>
            </div>
            <button onClick={runMatch} disabled={busy}>
              生成匹配
            </button>
          </div>
          <div className="table">
            <div className="row head grid-4">
              <span>属性</span>
              <span>表</span>
              <span>字段</span>
              <span>置信度</span>
            </div>
            {groupedMatches.map((group) => (
              <div key={group.classIri || group.className} className="group-block">
                <div className="group-header">
                  <span>类：{group.className}</span>
                  {group.classIri ? <small>{group.classIri}</small> : null}
                </div>
                {group.items.map((item) => {
                  const tableInfo = tables.find((table) => table.name === item.table_name);
                  const fields = tableInfo ? tableInfo.fields || [] : [];
                  return (
                    <div key={item.property_iri} className="row grid-4">
                      <div className="cell">
                        <span className="mono">{item.property_label || item.property_iri}</span>
                        <small>{item.property_iri}</small>
                      </div>
                      <select
                        value={item.table_name || ''}
                        onChange={(event) => updateTableSelection(item.property_iri, event.target.value)}
                      >
                        <option value="">-- 请选择表 --</option>
                        {tables.map((table) => (
                          <option key={table.name} value={table.name}>
                            {table.name}
                          </option>
                        ))}
                      </select>
                      <div className="field-select">
                        <select
                          value={item.field || ''}
                          onChange={(event) => updateFieldSelection(item.property_iri, event.target.value)}
                          disabled={!item.table_name}
                        >
                          <option value="">-- 请选择字段 --</option>
                          {fields.map((field) => (
                            <option key={field} value={field}>
                              {field}
                            </option>
                          ))}
                        </select>
                        {item.field && item.table_name && (
                          <small>
                            已选字段：{item.field}（{item.table_name}）
                          </small>
                        )}
                      </div>
                      <span>{formatScore(item.score)}</span>
                    </div>
                  );
                })}
              </div>
            ))}
            {!groupedMatches.length && <small>完成解析后生成匹配结果。</small>}
          </div>
        </article>

        <article className="card wide">
          <div className="card-head">
            <h2>4. 生成输出</h2>
            <span className="tag">ABox / R2RML</span>
          </div>
          <div className="actions">
            <button onClick={generateAbox} disabled={busy}>
              生成 ABox
            </button>
            <div className="mode">
              <label>
                表名
                <input
                  value={tableName}
                  onChange={(event) => setTableName(event.target.value)}
                />
              </label>
            </div>
            <button className="ghost" onClick={generateR2Rml} disabled={busy}>
              生成 R2RML
            </button>
          </div>
          <div className="output">
            <div className="output-head">
              <span>{output.format ? `格式：${output.format}` : '尚未生成输出'}</span>
              {output.content && (
                <button
                  className="ghost"
                  onClick={() => navigator.clipboard.writeText(output.content)}
                >
                  复制
                </button>
              )}
            </div>
            {output.filePath && (
              <div className="path">
                输出文件：<span className="mono">{output.filePath}</span>
              </div>
            )}
            <textarea
              value={output.content}
              readOnly
              placeholder="输出内容将显示在这里"
            />
          </div>
        </article>

        <article className="card">
          <div className="card-head">
            <h2>样例预览</h2>
            <span className="tag">预览</span>
          </div>
          <div className="preview">
            {tables.length ? (
              <div className="preview-block">
                <label>
                  表
                  <select
                    value={previewTable}
                    onChange={(event) => setPreviewTable(event.target.value)}
                  >
                    {tables.map((table) => (
                      <option key={table.name} value={table.name}>
                        {table.name}
                      </option>
                    ))}
                  </select>
                </label>
                {previewTableInfo ? (
                  <table>
                    <thead>
                      <tr>
                        {(previewTableInfo.fields || []).map((field) => (
                          <th key={field}>{field}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(previewTableInfo.sample_rows || []).map((row, index) => (
                        <tr key={index}>
                          {(previewTableInfo.fields || []).map((field) => (
                            <td key={field}>{row[field] ?? ''}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <small>暂无可预览表。</small>
                )}
              </div>
            ) : (
              <small>解析数据后展示样例。</small>
            )}
          </div>
        </article>
      </section>

      <footer className="footer">
        <span>前端版本：{FRONTEND_VERSION}</span>
        <span>后端版本：{backendVersion}</span>
      </footer>
    </div>
  );
}

const buildGraphData = (classes, objectProperties) => {
  const nodes = [];
  const nodeMap = new Map();

  const addNode = (item) => {
    if (!item || !item.iri) return;
    if (nodeMap.has(item.iri)) return;
    const label = item.label || item.local_name || item.iri;
    const node = {
      id: item.iri,
      label,
      x: GRAPH_WIDTH / 2 + (Math.random() - 0.5) * 120,
      y: GRAPH_HEIGHT / 2 + (Math.random() - 0.5) * 120
    };
    nodeMap.set(item.iri, node);
    nodes.push(node);
  };

  (classes || []).forEach(addNode);

  const links = [];
  (objectProperties || []).forEach((prop) => {
    const domains = prop.domains || [];
    const ranges = prop.ranges || [];
    domains.forEach((domain) => addNode(domain));
    ranges.forEach((range) => addNode(range));

    domains.forEach((domain) => {
      ranges.forEach((range) => {
        if (!domain?.iri || !range?.iri) return;
        const sourceNode = nodeMap.get(domain.iri);
        const targetNode = nodeMap.get(range.iri);
        if (!sourceNode || !targetNode) return;
        links.push({
          id: `${prop.iri}:${domain.iri}:${range.iri}`,
          source: sourceNode,
          target: targetNode,
          label: domain.label || domain.local_name || domain.iri
        });
      });
    });
  });

  return { nodes, links };
};

const getSvgPoint = (svg, event, width, height) => {
  const rect = svg.getBoundingClientRect();
  const scaleX = width / rect.width;
  const scaleY = height / rect.height;
  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY
  };
};
