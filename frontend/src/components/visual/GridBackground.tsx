import { useEffect, useRef } from 'react'

export function GridBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    // Particle system
    const particles: { x: number; y: number; vx: number; vy: number; size: number; opacity: number }[] = []
    for (let i = 0; i < 30; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 2 + 1,
        opacity: Math.random() * 0.3 + 0.1,
      })
    }

    let frame = 0
    const animate = () => {
      frame++
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Grid lines
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.03)'
      ctx.lineWidth = 1
      const gridSize = 50

      for (let x = 0; x < canvas.width; x += gridSize) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, canvas.height)
        ctx.stroke()
      }
      for (let y = 0; y < canvas.height; y += gridSize) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(canvas.width, y)
        ctx.stroke()
      }

      // Animated particles
      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0) p.x = canvas.width
        if (p.x > canvas.width) p.x = 0
        if (p.y < 0) p.y = canvas.height
        if (p.y > canvas.height) p.y = 0

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(0, 212, 255, ${p.opacity})`
        ctx.fill()
      })

      // Central radar pulse
      const centerX = canvas.width * 0.15
      const centerY = canvas.height * 0.3
      const maxRadius = 200
      const pulseRadius = ((frame * 2) % maxRadius)
      const pulseOpacity = 0.15 * (1 - pulseRadius / maxRadius)

      ctx.beginPath()
      ctx.arc(centerX, centerY, pulseRadius, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(0, 255, 136, ${pulseOpacity})`
      ctx.lineWidth = 2
      ctx.stroke()

      // Secondary pulse
      const pulse2Radius = ((frame * 1.5 + 100) % maxRadius)
      const pulse2Opacity = 0.1 * (1 - pulse2Radius / maxRadius)
      ctx.beginPath()
      ctx.arc(centerX, centerY, pulse2Radius, 0, Math.PI * 2)
      ctx.strokeStyle = `rgba(0, 212, 255, ${pulse2Opacity})`
      ctx.stroke()

      requestAnimationFrame(animate)
    }
    animate()

    return () => {
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ opacity: 0.6 }}
    />
  )
}