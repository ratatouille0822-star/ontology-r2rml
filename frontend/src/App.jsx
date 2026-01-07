import React, { useEffect, useMemo, useState } from 'react';

const FRONTEND_VERSION = 'v0.1.0-内测';
const emptyOutput = { format: '', content: '', filePath: '' };

const formatScore = (value) => {
  if (value === null || value === undefined) return '-';
  return `${Math.round(value * 100)}%`;
};

export default function App() {
  const [tboxFile, setTboxFile] = useState(null);
  const [tboxProps, setTboxProps] = useState([]);
  const [dataFiles, setDataFiles] = useState([]);
  const [directoryMode, setDirectoryMode] = useState(false);
  const [fields, setFields] = useState([]);
  const [sampleRows, setSampleRows] = useState([]);
  const [allRows, setAllRows] = useState([]);
  const [fileCount, setFileCount] = useState(0);
  const [matches, setMatches] = useState([]);
  const [matchMode, setMatchMode] = useState('llm');
  const [output, setOutput] = useState(emptyOutput);
  const [status, setStatus] = useState('');
  const [sourceType, setSourceType] = useState('file');
  const [jdbcInfo, setJdbcInfo] = useState({ url: '', user: '', password: '' });
  const [tableName, setTableName] = useState('data_table');
  const [backendVersion, setBackendVersion] = useState('未连接');
  const [busy, setBusy] = useState(false);

  const propertyOptions = useMemo(() => tboxProps, [tboxProps]);

  const mappingPayload = useMemo(() => {
    return matches
      .filter((item) => item.property_iri)
      .map((item) => ({ field: item.field, property_iri: item.property_iri }));
  }, [matches]);

  const fileListLabel = useMemo(() => {
    if (!dataFiles.length) return '未选择文件';
    const names = dataFiles
      .slice(0, 3)
      .map((file) => file.webkitRelativePath || file.name)
      .join('、');
    return dataFiles.length > 3 ? `${names} 等 ${dataFiles.length} 个文件` : names;
  }, [dataFiles]);

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
      setTboxProps(data.properties || []);
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
      setFields(data.columns || []);
      setSampleRows(data.sample_rows || []);
      setAllRows(data.rows || []);
      setFileCount(data.file_count || dataFiles.length);
      handleStatus(`已解析字段：${data.columns?.length || 0}，文件数：${data.file_count || dataFiles.length}`);
    } catch (error) {
      handleStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  const runMatch = async () => {
    if (!fields.length || !tboxProps.length) {
      handleStatus('请先完成 TBox 与数据解析');
      return;
    }
    setBusy(true);
    try {
      const response = await fetch('/api/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields, properties: tboxProps, mode: matchMode })
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

  const updateMatch = (field, propertyIri) => {
    setMatches((prev) =>
      prev.map((item) =>
        item.field === field ? { ...item, property_iri: propertyIri } : item
      )
    );
  };

  const generateAbox = async () => {
    if (!mappingPayload.length || !allRows.length) {
      handleStatus('请先完成匹配并确保有数据');
      return;
    }
    setBusy(true);
    try {
      const response = await fetch('/api/abox', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: allRows, mapping: mappingPayload })
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
    setTboxProps([]);
    setDataFiles([]);
    setFields([]);
    setSampleRows([]);
    setAllRows([]);
    setFileCount(0);
    setMatches([]);
    setOutput(emptyOutput);
    setStatus('');
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
          <div className="list">
            {tboxProps.slice(0, 6).map((prop) => (
              <div key={prop.iri}>
                <p className="mono">{prop.label || prop.local_name}</p>
                <small>{prop.iri}</small>
              </div>
            ))}
            {!tboxProps.length && <small>等待上传解析</small>}
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
            <span>字段数量</span>
            <strong>{fields.length}</strong>
          </div>
          <div className="summary">
            <span>文件数量</span>
            <strong>{fileCount}</strong>
          </div>

          <div className="list">
            {fields.slice(0, 6).map((field) => (
              <div key={field}>
                <p className="mono">{field}</p>
              </div>
            ))}
            {!fields.length && <small>等待数据源解析</small>}
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
            <button onClick={runMatch} disabled={busy}>
              生成匹配
            </button>
          </div>
          <div className="table">
            <div className="row head">
              <span>字段</span>
              <span>匹配属性</span>
              <span>置信度</span>
            </div>
            {matches.map((item) => (
              <div key={item.field} className="row">
                <span className="mono">{item.field}</span>
                <select
                  value={item.property_iri || ''}
                  onChange={(event) => updateMatch(item.field, event.target.value)}
                >
                  <option value="">-- 请选择属性 --</option>
                  {propertyOptions.map((prop) => (
                    <option key={prop.iri} value={prop.iri}>
                      {prop.label || prop.local_name}
                    </option>
                  ))}
                </select>
                <span>{formatScore(item.score)}</span>
              </div>
            ))}
            {!matches.length && <small>完成解析后生成匹配结果。</small>}
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
            {sampleRows.length ? (
              <table>
                <thead>
                  <tr>
                    {fields.map((field) => (
                      <th key={field}>{field}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sampleRows.map((row, index) => (
                    <tr key={index}>
                      {fields.map((field) => (
                        <td key={field}>{row[field] ?? ''}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
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
