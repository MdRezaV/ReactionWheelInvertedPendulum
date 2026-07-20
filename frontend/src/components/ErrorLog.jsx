import { useCallback, useEffect, useRef, useState } from 'react'
import * as Collapsible from '@radix-ui/react-collapsible'
import { toPersianDigits } from '../utils/format'

const MAX_VISIBLE = 50

function formatTimestamp(ts) {
  const d = new Date(ts)
  return toPersianDigits(d.toLocaleTimeString('fa-IR', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0'))
}

export default function ErrorLog({ errors, onClear }) {
  const [collapsed, setCollapsed] = useState(true)
  const listRef = useRef(null)

  useEffect(() => {
    if (!collapsed && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [errors, collapsed])

  const count = errors.length

  return (
    <Collapsible.Root open={!collapsed} onOpenChange={(open) => setCollapsed(!open)} className="border-t border-border flex-shrink-0 text-[13px] bg-surface/60 backdrop-blur-sm">
      <Collapsible.Trigger className="flex items-center justify-between w-full px-4 py-1 cursor-pointer select-none hover:bg-white/[0.02] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-accent">
        <span className="flex items-center gap-1.5 font-bold text-text-dim">
          خطاها
          {count > 0 && (
            <span className="bg-danger text-white text-[9px] font-bold px-1 py-px rounded-full min-w-[14px] text-center">
              {count > 99 ? '99+' : count}
            </span>
          )}
        </span>
        <span className="text-text-dim text-[11px] transition-transform duration-150 data-[state=open]:rotate-180">▲</span>
      </Collapsible.Trigger>
      <Collapsible.Content className="border-t border-border max-h-[120px] flex flex-col animate-[slide-down_150ms_ease-out]">
          {count === 0 ? (
            <div className="px-3 py-1.5 text-text-dim italic">بدون خطا</div>
          ) : (
            <>
              <div className="flex justify-end px-2 py-0.5">
                <button
                  onClick={onClear}
                  className="px-2 py-0.5 text-[12px] rounded border border-border bg-card text-text-dim cursor-pointer hover:text-text-h hover:border-accent-border transition-colors"
                >
                  پاک کردن
                </button>
              </div>
              <div className="overflow-y-auto px-2 pb-1.5 flex-1" ref={listRef}>
                {errors.slice(-MAX_VISIBLE).map((err, i) => (
                  <div key={err.time + '-' + i} className="flex gap-2 py-px font-mono text-[12px] leading-relaxed">
                    <span className="text-text-dim flex-shrink-0" dir="ltr">{formatTimestamp(err.time)}</span>
                    <span className="text-red-300 break-words">{err.message}</span>
                  </div>
                ))}
              </div>
            </>
          )}
      </Collapsible.Content>
    </Collapsible.Root>
  )
}