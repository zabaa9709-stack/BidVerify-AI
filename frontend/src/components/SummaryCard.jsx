import { useEffect, useState } from "react"

function useCountUp(target, duration = 650) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (typeof target !== "number" || isNaN(target) || target <= 0) {
      return
    }

    let startTime = null
    let animationFrameId
    const startVal = 0

    const step = (timestamp) => {
      if (!startTime) startTime = timestamp
      const elapsed = timestamp - startTime
      const progress = Math.min(elapsed / duration, 1)
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = Math.round(startVal + (target - startVal) * eased)
      setCount(current)

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(step)
      } else {
        setCount(target)
      }
    }

    animationFrameId = requestAnimationFrame(step)
    return () => cancelAnimationFrame(animationFrameId)
  }, [target, duration])

  if (typeof target !== "number" || isNaN(target) || target <= 0) {
    return target
  }

  return count
}

export default function SummaryCard({ type, label, value, description, icon }) {
  const animatedValue = useCountUp(value)

  return (
    <div className={`kpi-card kpi-${type} card-interactive`}>
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        <div className="kpi-icon-wrap">
          {icon}
        </div>
      </div>
      <div className="kpi-number count-animated">
        {value !== undefined && value !== null ? animatedValue : "—"}
      </div>
      {description && <div className="kpi-desc">{description}</div>}
    </div>
  )
}
