import { useEffect } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import { Extension, type JSONContent } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Placeholder from '@tiptap/extension-placeholder';
import { Bold, Code, Italic, Link2, List, ListOrdered, Redo2, Strikethrough, UnderlineIcon, Undo2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useReducedMotionPreference } from '@/hooks/useReducedMotionPreference';

type ChangePayload = { content_json: Record<string, unknown>; content_markdown: string; plain_text: string };

const StableBlockId = Extension.create({
  name: 'stableBlockId',
  addGlobalAttributes() {
    return [{
      types: ['paragraph', 'heading', 'bulletList', 'orderedList', 'taskList', 'blockquote', 'codeBlock'],
      attributes: {
        blockId: {
          default: null,
          parseHTML: (element) => element.getAttribute('data-block-id'),
          renderHTML: (attributes) => attributes.blockId ? { 'data-block-id': attributes.blockId } : {},
        },
      },
    }];
  },
  onCreate() { assignMissingBlockIds(this.editor); },
  onTransaction() { assignMissingBlockIds(this.editor); },
});

function assignMissingBlockIds(editor: ReturnType<typeof useEditor>) {
  if (!editor || editor.isDestroyed) return;
  const transaction = editor.state.tr;
  let changed = false;
  editor.state.doc.forEach((node, offset) => {
    if (!node.attrs.blockId) {
      transaction.setNodeMarkup(offset, undefined, { ...node.attrs, blockId: crypto.randomUUID() });
      changed = true;
    }
  });
  if (changed) editor.view.dispatch(transaction.setMeta('addToHistory', false));
}

function textNode(text: string): JSONContent[] { return text ? [{ type: 'text', text }] : []; }

export function markdownToTiptap(markdown: string): JSONContent {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const content: JSONContent[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.startsWith('```')) {
      const language = line.slice(3).trim() || null; const body: string[] = []; index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) body.push(lines[index++]);
      content.push({ type: 'codeBlock', attrs: { language, blockId: crypto.randomUUID() }, content: textNode(body.join('\n')) }); index += 1; continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) { content.push({ type: 'heading', attrs: { level: heading[1].length, blockId: crypto.randomUUID() }, content: textNode(heading[2]) }); index += 1; continue; }
    const task = /^\s*[-*]\s+\[([ xX])\]\s+(.*)$/.exec(line);
    if (task) { const items: JSONContent[] = []; while (index < lines.length) { const match = /^\s*[-*]\s+\[([ xX])\]\s+(.*)$/.exec(lines[index]); if (!match) break; items.push({ type: 'taskItem', attrs: { checked: match[1].toLowerCase() === 'x' }, content: [{ type: 'paragraph', content: textNode(match[2]) }] }); index += 1; } content.push({ type: 'taskList', attrs: { blockId: crypto.randomUUID() }, content: items }); continue; }
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    if (bullet) { const items: JSONContent[] = []; while (index < lines.length) { const match = /^\s*[-*]\s+(.*)$/.exec(lines[index]); if (!match) break; items.push({ type: 'listItem', content: [{ type: 'paragraph', content: textNode(match[1]) }] }); index += 1; } content.push({ type: 'bulletList', attrs: { blockId: crypto.randomUUID() }, content: items }); continue; }
    const ordered = /^\s*\d+\.\s+(.*)$/.exec(line);
    if (ordered) { const items: JSONContent[] = []; while (index < lines.length) { const match = /^\s*\d+\.\s+(.*)$/.exec(lines[index]); if (!match) break; items.push({ type: 'listItem', content: [{ type: 'paragraph', content: textNode(match[1]) }] }); index += 1; } content.push({ type: 'orderedList', attrs: { start: 1, blockId: crypto.randomUUID() }, content: items }); continue; }
    if (line.startsWith('> ')) { content.push({ type: 'blockquote', attrs: { blockId: crypto.randomUUID() }, content: [{ type: 'paragraph', content: textNode(line.slice(2)) }] }); index += 1; continue; }
    if (!line.trim()) { index += 1; continue; }
    const paragraph = [line]; index += 1; while (index < lines.length && lines[index].trim() && !/^(#{1,6})\s|^```|^\s*[-*]\s|^\s*\d+\.\s|^> /.test(lines[index])) paragraph.push(lines[index++]);
    content.push({ type: 'paragraph', attrs: { blockId: crypto.randomUUID() }, content: textNode(paragraph.join('\n')) });
  }
  return { type: 'doc', content: content.length ? content : [{ type: 'paragraph', attrs: { blockId: crypto.randomUUID() } }] };
}

function inlineMarkdown(node: JSONContent): string {
  let value = node.text ?? (node.content ?? []).map(inlineMarkdown).join('');
  for (const mark of node.marks ?? []) {
    if (mark.type === 'bold') value = `**${value}**`; else if (mark.type === 'italic') value = `*${value}*`; else if (mark.type === 'underline') value = `<u>${value}</u>`; else if (mark.type === 'strike') value = `~~${value}~~`; else if (mark.type === 'code') value = `\`${value}\``; else if (mark.type === 'link') value = `[${value}](${String(mark.attrs?.href ?? '')})`;
  }
  return value;
}

export function tiptapToMarkdown(doc: JSONContent): string {
  const render = (node: JSONContent, depth = 0): string => {
    const body = (node.content ?? []).map((child) => render(child, depth + 1)).join('');
    if (node.type === 'text') return inlineMarkdown(node);
    if (node.type === 'hardBreak') return '  \n';
    if (node.type === 'heading') return `${'#'.repeat(Number(node.attrs?.level ?? 1))} ${body}\n\n`;
    if (node.type === 'paragraph') return `${body}\n`;
    if (node.type === 'blockquote') return body.trim().split('\n').map((line) => `> ${line}`).join('\n') + '\n\n';
    if (node.type === 'codeBlock') return `\`\`\`${String(node.attrs?.language ?? '')}\n${body}\n\`\`\`\n\n`;
    if (node.type === 'bulletList' || node.type === 'orderedList' || node.type === 'taskList') return `${body}\n`;
    if (node.type === 'listItem') return `${node.attrs?.checked === true ? '- [x] ' : node.attrs?.checked === false ? '- [ ] ' : '- '}${body.trim()}\n`;
    if (node.type === 'taskItem') return `${node.attrs?.checked ? '- [x] ' : '- [ ] '}${body.trim()}\n`;
    return body;
  };
  return render(doc).replace(/\n{3,}/g, '\n\n').trim();
}

function Tool({ active, label, onClick, children }: { active?: boolean; label: string; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" aria-label={label} title={label} onClick={onClick} className={cn('rounded p-1.5 text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary', active && 'bg-accent text-primary')}>{children}</button>;
}

export default function RichNoteEditor({ noteId, contentJson, markdown, citationBlockId, onChange }: { noteId: string; contentJson: Record<string, unknown> | null; markdown: string; citationBlockId?: string | null; onChange: (change: ChangePayload) => void }) {
  const prefersReducedMotion = useReducedMotionPreference();
  const editor = useEditor({
    extensions: [StarterKit.configure({ link: false, underline: false }), Underline, Link.configure({ openOnClick: false, HTMLAttributes: { rel: 'noopener noreferrer' } }), TaskList, TaskItem.configure({ nested: true }), Placeholder.configure({ placeholder: 'Start writing…' }), StableBlockId],
    content: contentJson?.type === 'doc' ? contentJson as JSONContent : markdownToTiptap(markdown),
    editorProps: { attributes: { class: 'cial-note-editor min-h-[26rem] px-1 py-2 text-[15px] leading-7 text-foreground outline-none' } },
    onUpdate: ({ editor: instance, transaction }) => { if (transaction.getMeta('addToHistory') === false) return; const json = instance.getJSON(); onChange({ content_json: json as Record<string, unknown>, content_markdown: tiptapToMarkdown(json), plain_text: instance.getText({ blockSeparator: '\n' }) }); },
  }, [noteId]);

  useEffect(() => {
    if (!editor || !citationBlockId) return;
    requestAnimationFrame(() => { const element = document.querySelector(`[data-block-id="${CSS.escape(citationBlockId)}"]`); element?.scrollIntoView({ block: 'center', behavior: prefersReducedMotion ? 'auto' : 'smooth' }); element?.classList.add('note-citation-highlight'); window.setTimeout(() => element?.classList.remove('note-citation-highlight'), 2400); });
  }, [editor, citationBlockId, prefersReducedMotion]);
  if (!editor) return null;
  const setLink = () => { const current = editor.getAttributes('link').href as string | undefined; const href = window.prompt('Link URL', current ?? 'https://'); if (href === null) return; if (!href.trim()) editor.chain().focus().unsetLink().run(); else editor.chain().focus().extendMarkRange('link').setLink({ href: href.trim() }).run(); };
  return <div className="relative">
    <div className="mb-2 flex flex-wrap items-center gap-1 border-b border-border pb-2" aria-label="Editor controls">
      <Tool label="Undo" onClick={() => editor.chain().focus().undo().run()}><Undo2 size={15}/></Tool><Tool label="Redo" onClick={() => editor.chain().focus().redo().run()}><Redo2 size={15}/></Tool>
      <Tool label="Bulleted list" active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}><List size={15}/></Tool><Tool label="Numbered list" active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered size={15}/></Tool><Tool label="Code block" active={editor.isActive('codeBlock')} onClick={() => editor.chain().focus().toggleCodeBlock().run()}><Code size={15}/></Tool>
    </div>
    <BubbleMenu editor={editor}><div className="flex items-center gap-0.5 rounded-lg border border-border bg-card p-1 shadow-md"><Tool label="Bold" active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}><Bold size={14}/></Tool><Tool label="Italic" active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}><Italic size={14}/></Tool><Tool label="Underline" active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}><UnderlineIcon size={14}/></Tool><Tool label="Strikethrough" active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()}><Strikethrough size={14}/></Tool><Tool label="Link" active={editor.isActive('link')} onClick={setLink}><Link2 size={14}/></Tool></div></BubbleMenu>
    <EditorContent editor={editor}/>
  </div>;
}
