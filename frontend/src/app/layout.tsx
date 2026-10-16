import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AirCreator - 3D Aircraft Modeling Studio',
  description: 'Modelagem 3D e reconstrução aeronáutica automatizada a partir de blueprints',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="antialiased bg-slate-950 overflow-hidden">{children}</body>
    </html>
  );
}
