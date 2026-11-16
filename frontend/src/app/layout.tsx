import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Clipper Pro Studio - 3D Autonomous Repurposing Engine',
  description: 'Convert long-form podcasts and videos into viral 9:16 shorts with 3D WebGL preview, AI face tracking, and karaoke captions.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased selection:bg-purple-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
