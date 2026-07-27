import { zoomStyle } from './highlight-utils';

interface ImageViewerProps {
  src: string;
  title: string;
  zoomLevel: number;
}

export default function ImageViewer({ src, title, zoomLevel }: ImageViewerProps) {
  return (
    <div className="scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border bg-muted p-4">
      <div style={zoomStyle(zoomLevel)}>
        <img src={src} alt={title} className="w-full rounded-xl object-contain" />
      </div>
    </div>
  );
}
