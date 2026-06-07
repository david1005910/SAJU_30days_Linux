import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '사주공학 대시보드',
  description: 'YouTube 자동화 파이프라인 운영 대시보드',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  )
}
