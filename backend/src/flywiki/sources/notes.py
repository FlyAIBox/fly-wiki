import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flywiki.sources.models import EditableNote, NoteVersion
from flywiki.sources.repository import SourceRepository, SourceResourceNotFound


class NoteVersionConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class EditableNoteView:
    note: EditableNote
    current_version: NoteVersion
    history: tuple[NoteVersion, ...]


class EditableNoteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = SourceRepository(session)

    async def create_initial(
        self,
        workspace_id: uuid.UUID,
        source_version_id: uuid.UUID,
        markdown: str,
    ) -> EditableNoteView:
        await self._repository.get_version(workspace_id, source_version_id)
        existing = await self._repository.find_note_by_source_version(
            workspace_id, source_version_id
        )
        if existing is not None:
            return await self.get(workspace_id, existing.id)

        note_id = uuid.uuid5(source_version_id, "editable-note")
        note = EditableNote(
            id=note_id,
            workspace_id=workspace_id,
            source_version_id=source_version_id,
        )
        version = NoteVersion(
            id=uuid.uuid5(note_id, "version:1"),
            workspace_id=workspace_id,
            note_id=note_id,
            version_number=1,
            markdown=markdown,
        )
        self._session.add_all([note, version])
        await self._session.commit()
        return EditableNoteView(note, version, (version,))

    async def save(
        self,
        workspace_id: uuid.UUID,
        note_id: uuid.UUID,
        markdown: str,
        *,
        base_version_number: int,
    ) -> EditableNoteView:
        if not markdown.strip():
            raise ValueError("Editable Note markdown must not be empty")
        note = await self._session.scalar(
            select(EditableNote)
            .where(
                EditableNote.workspace_id == workspace_id,
                EditableNote.id == note_id,
            )
            .with_for_update()
        )
        if note is None:
            raise SourceResourceNotFound("Editable Note not found")

        current = await self._repository.get_latest_note_version(workspace_id, note_id)
        if current.version_number != base_version_number:
            raise NoteVersionConflict(
                f"current version is {current.version_number}, not {base_version_number}"
            )
        version = NoteVersion(
            workspace_id=workspace_id,
            note_id=note_id,
            version_number=current.version_number + 1,
            markdown=markdown,
        )
        self._session.add(version)
        await self._session.commit()
        return await self.get(workspace_id, note_id)

    async def get(self, workspace_id: uuid.UUID, note_id: uuid.UUID) -> EditableNoteView:
        note = await self._repository.get_note(workspace_id, note_id)
        history = await self._repository.list_note_versions(workspace_id, note_id)
        if not history:
            raise RuntimeError("Editable Note has no versions")
        return EditableNoteView(note, history[-1], tuple(history))
