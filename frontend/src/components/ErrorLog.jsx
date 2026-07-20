import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_VISIBLE = 50

function formatTimestamp(ts) {
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0')
}

export default function ErrorLog({ errors, onClear }) {
  const [collapsed, setCollapsed] = useState(true)
  const listRef = useRef(null)

  const toggle = useCallback(() => {
    setCollapsed((c) => !c)
  }, [])

  useEffect(() => {
    if (!collapsed && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [errors, collapsed])

  const count = errors.length

  return (
    <div className={`error-log ${collapsed ? 'collapsed' : ''}`}>
      <div className="error-log-header" onClick={toggle}>
        <span className="error-log-title">
          Errors
          {count > 0 && <span className="error-badge">{count > 99 ? '99+' : count}</span>}
        </span>
        <span className="error-log-toggle">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="error-log-body">
          {count === 0 ? (
            <div className="error-log-empty">No errors</div>
          ) : (
            <>
              <div className="error-log-actions">
                <button onClick={onClear}>Clear</button>
              </div>
              <div className="error-log-list" ref={listRef}>
                {errors.slice(-MAX_VISIBLE).map((err, i) => (
                  <div key={err.time + '-' + i} className="error-log-entry">
                    <span className="error-log-time">{formatTimestamp(err.time)}</span>
                    <span className="error-log-msg">{err.message}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}