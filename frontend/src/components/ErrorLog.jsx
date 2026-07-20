import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_VISIBLE = 50

function formatTimestamp(ts) {
  const d = new Date(ts)
  return d.toLocaleTimeString('fa-IR', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0')
}

export default function ErrorLog({ errors, onClear }) {
  const [collapsed, setCollapsed] = useState(true)
  const listRef = useRef(null)

  const toggle = useCallback(() => { setCollapsed((c) => !c) }, [])

  useEffect(() => {
    if (!collapsed && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [errors, collapsed])

  const count = errors.length

  return (
    <div className="border-t border-border flex-shrink-0 text-xs bg-surface/80 backdrop-blur-sm">
      <div className="flex items-center justify-between px-6 py-1.5 cursor-pointer select-none hover:bg-white/[0.03] transition-colors" onClick={toggle}>
        <span className="flex items-center gap-2 font-bold text-text-dim">
          خطاها
          {count > 0 && (
            <span className="bg-danger text-white text-[10px] font-bold px-1.5 py-px rounded-full min-w-[18px] text-center">
              {count > 99 ? '۹۹+' : count}
            </span>
          )}
        </span>
        <span className="text-text-dim text-[10px]">{collapsed ? '◀' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="border-t border-border max-h-[160px] flex flex-col">
          {count === 0 ? (
            <div className="px-4 py-2 text-text-dim italic">بدون خطا</div>
          ) : (
            <>
              <div className="flex justify-end px-3 py-1">
                <button
                  onClick={onClear}
                  className="px-2.5 py-0.5 text-[11px] rounded border border-border bg-card text-text-dim cursor-pointer hover:text-text-h hover:border-accent-border transition-colors"
                >
                  پاک کردن
                </button>
              </div>
              <div className="overflow-y-auto px-3 pb-2 flex-1" ref={listRef}>
                {errors.slice(-MAX_VISIBLE).map((err, i) => (
                  <div key={err.time + '-' + i} className="flex gap-2.5 py-0.5 font-mono text-[11px] leading-relaxed">
                    <span className="text-text-dim flex-shrink-0" dir="ltr">{formatTimestamp(err.time)}</span>
                    <span className="text-red-300 break-words">{err.message}</span>
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