import ReactMarkdown from 'react-markdown'
export default function BoardBody({ body }: { body: string }) {
    return <div className="break-words text-[15px] leading-7 [&_p]:mb-4 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:list-decimal [&_ol]:pl-6 [&_h2]:text-xl [&_h2]:font-bold [&_h2]:my-4 [&_blockquote]:border-l-4 [&_blockquote]:pl-4 [&_pre]:overflow-x-auto [&_pre]:bg-slate-100 [&_pre]:p-4">
        <ReactMarkdown skipHtml allowedElements={['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'blockquote', 'code', 'pre', 'h2', 'h3', 'hr']}
            components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-800 underline">{children}</a> }}>
            {body}
        </ReactMarkdown>
    </div>
}
