// Copyright (C) 2026 Homer contributors
// SPDX-License-Identifier: AGPL-3.0-only
// Narrow access to extension-created memories, never a general lorebook editor.
export function createHomerMemoryAccess({ binding, chatKey, load, save, writeLane, changed }) {
    const isMemory = entry => entry?.stmemorybooks === true;
    const revision = entry => JSON.stringify(entry);
    const check = snapshot => {
        if (snapshot.chatKey !== chatKey() || snapshot.book !== binding()) {
            throw new Error('对话已切换，请返回当前对话重新打开记忆。');
        }
    };
    return {
        async list() {
            const snapshot = { chatKey: chatKey(), book: binding() };
            if (!snapshot.book) return { ...snapshot, items: [] };
            const data = await load(snapshot.book);
            check(snapshot);
            if (!data?.entries) throw new Error('暂时无法读取记忆，请重试。');
            return { ...snapshot, items: Object.entries(data.entries).filter(([,entry])=>isMemory(entry)).map(([id,entry])=>({
                id, title: String(entry.comment || '未命名记忆'), content: String(entry.content || ''),
                disabled: !!entry.disable, revision: revision(entry),
            })) };
        },
        async update(snapshot, item, changes) {
            check(snapshot);
            if (!snapshot.book) throw new Error('当前对话还没有记忆。');
            return writeLane([snapshot.book], async () => {
                check(snapshot);
                const loaded = await load(snapshot.book);
                check(snapshot);
                const data = structuredClone(loaded);
                const entry = data?.entries?.[item.id];
                if (!isMemory(entry)) throw new Error('这条记忆已不存在，请重新打开列表。');
                if (revision(entry) !== item.revision) throw new Error('记忆已发生变化，请重新打开后再编辑。');
                if (changes.remove === true) delete data.entries[item.id];
                else {
                    const title=String(changes.title ?? item.title).trim(), content=String(changes.content ?? item.content).trim();
                    if (!content || content.length>100000 || !title || title.length>500) throw new Error('请填写记忆内容和标题，标题不超过 500 字，内容不超过 10 万字。');
                    entry.comment=title; entry.content=content;
                    if (typeof changes.disabled==='boolean') entry.disable=changes.disabled;
                }
                await save(snapshot.book,data,true);
                changed();
            });
        },
    };
}
