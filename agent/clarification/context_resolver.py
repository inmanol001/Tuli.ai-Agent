from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.gateway.message_types import ContextPackage
from agent.gateway.session_manager import SessionState


class ContextEntity(BaseModel):
    value: str
    kind: str
    source_role: str | None = None
    history_index: int | None = None
    confidence: str = "low"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextResolutionResult(BaseModel):
    has_vague_reference: bool
    has_status_question: bool
    resolved_reference: str | None = None
    candidates: list[str] = Field(default_factory=list)
    confidence: Literal["none", "low", "high", "ambiguous"]
    reason: str
    recent_tool_result: dict[str, Any] | None = None
    entities: list[ContextEntity] = Field(default_factory=list)


class ContextResolver:
    """
    ContextResolver no debe funcionar como lista cerrada de marcas/apps.

    Responsabilidad:
    - detectar referencias vagas
    - detectar preguntas de estado
    - extraer entidades recientes desde patrones abiertos
    - separar entidades del mensaje actual vs historial
    - no resolver una plataforma explícita como si fuera el objeto vago
    """

    _status_question_patterns = (
        r"\bse\s+ejecut[oó]\b",
        r"\bse\s+aplic[oó]\b",
        r"\bqued[oó]\s+abiert[oa]\b",
        r"\bp[aá]gina\s+qued[oó]\s+abiert[oa]\b",
        r"\btermin[oó]\b",
        r"\btermin[oó]\s+correctamente\b",
        r"\bya\s+lo\s+hiciste\b",
        r"\bya\s+hiciste\b",
        r"\bya\s+buscaste\b",
        r"\bya\s+abriste\b",
        r"\bqued[oó]\s+list[oa]\b",
    )

    _vague_reference_patterns = (
        r"\besto\b",
        r"\beso\b",
        r"\besta\b",
        r"\beste\b",
        r"\besa\b",
        r"\bese\b",
        r"\b[aá]brel[ao]\b",
        r"\babrel[ao]\b",
        r"\b[uú]sal[ao]\b",
        r"\busal[ao]\b",
        r"\bhazlo\b",
        r"\bla\s+otra\b",
        r"\bel\s+otro\b",
        r"\bel\s+mismo\b",
        r"\bla\s+misma\b",
        r"\bel\s+primero\b",
        r"\bla\s+primera\b",
        r"\bsegunda\s+opci[oó]n\b",
        r"\bcomo\s+antes\b",
        r"\bcomo\s+la\s+vez\s+pasada\b",
        r"\bdonde\s+nos\s+quedamos\b",
        r"\blo\s+anterior\b",
        r"\bel\s+anterior\b",
        r"\bla\s+anterior\b",
        r"\bahorita\b",
        r"\bmencionad[oa]\b",
        r"\bla\s+que\s+(te\s+)?mencion[eé]\b",
        r"\bla\s+que\s+(te\s+)?mencione\b",
    )

    # Estas listas quedan solo como fallback secundario, no como mecanismo principal.
    _known_sites = ("Canva", "GitHub", "YouTube", "Google", "Ollama", "OpenAI")
    _known_apps = (
        "Google Chrome",
        "Chrome",
        "Safari",
        "Visual Studio Code",
        "VSCode",
        "Terminal",
        "Finder",
        "Notes",
    )

    _entity_stopwords = {
        "",
        "eso",
        "esto",
        "esa",
        "ese",
        "esta",
        "este",
        "la",
        "el",
        "lo",
        "un",
        "una",
        "algo",
        "otra cosa",
        "otro",
        "otra",
        "después",
        "despues",
        "ahora",
        "hoy",
        "mañana",
        "manana",
        "también",
        "tambien",
        "para",
        "con",
        "en",
        "a",
        "de",
        "que",
    }

    def resolve(
        self,
        context: ContextPackage,
        session: SessionState | None = None,
    ) -> ContextResolutionResult:
        text = self._normalized_text(context.user_message)

        history_entities = self._extract_history_entities(context)
        current_entities = self._extract_current_entities(context)

        entities = [*current_entities, *history_entities]
        all_candidates = self._dedupe_candidates([entity.value for entity in entities])

        # Para resolver referencias vagas, priorizar entidades declaradas por el usuario
        # y evidencia de tools. El assistant solo debe usarse como fallback final.
        primary_history_entities = [
            entity for entity in history_entities
            if entity.source_role in {"user", "tool"}
        ]
        secondary_history_entities = [
            entity for entity in history_entities
            if entity.source_role not in {"user", "tool"}
        ]

        primary_history_candidates = self._dedupe_candidates(
            [entity.value for entity in primary_history_entities]
        )
        secondary_history_candidates = self._dedupe_candidates(
            [entity.value for entity in secondary_history_entities]
        )
        history_candidates = primary_history_candidates or secondary_history_candidates

        recent_tool_result = self._recent_tool_result(context)
        has_vague_reference = self._has_vague_reference(text)
        has_status_question = self._has_status_question(text)

        current_platforms = self._explicit_platforms_in_current_message(context.user_message)
        content_transfer_missing_object = (
            self._has_content_transfer_intent(text)
            and self._has_vague_content_object(text)
            and bool(current_platforms)
        )

        if has_status_question:
            if recent_tool_result is not None:
                return ContextResolutionResult(
                    has_vague_reference=has_vague_reference,
                    has_status_question=True,
                    resolved_reference=None,
                    candidates=all_candidates,
                    confidence="high",
                    reason="recent_tool_result_available",
                    recent_tool_result=recent_tool_result,
                    entities=entities,
                )
            return ContextResolutionResult(
                has_vague_reference=has_vague_reference,
                has_status_question=True,
                resolved_reference=None,
                candidates=all_candidates,
                confidence="none",
                reason="missing_recent_tool_result",
                recent_tool_result=None,
                entities=entities,
            )

        if content_transfer_missing_object:
            # En "monta ese texto en X", X es plataforma explícita, no el objeto referido.
            filtered_history_candidates = [
                candidate
                for candidate in history_candidates
                if self._normalized_text(candidate)
                not in {self._normalized_text(p) for p in current_platforms}
            ]

            if not filtered_history_candidates:
                return ContextResolutionResult(
                    has_vague_reference=True,
                    has_status_question=False,
                    resolved_reference=None,
                    candidates=[],
                    confidence="none",
                    reason="explicit_platform_missing_content",
                    recent_tool_result=recent_tool_result,
                    entities=entities,
                )

            if len(filtered_history_candidates) == 1:
                return ContextResolutionResult(
                    has_vague_reference=True,
                    has_status_question=False,
                    resolved_reference=filtered_history_candidates[0],
                    candidates=filtered_history_candidates,
                    confidence="high",
                    reason="single_recent_content_reference",
                    recent_tool_result=recent_tool_result,
                    entities=entities,
                )

            return ContextResolutionResult(
                has_vague_reference=True,
                has_status_question=False,
                resolved_reference=None,
                candidates=filtered_history_candidates,
                confidence="ambiguous",
                reason="multiple_recent_content_references",
                recent_tool_result=recent_tool_result,
                entities=entities,
            )

        if has_vague_reference:
            # Para referencias vagas, resolver principalmente contra historial.
            # No usar entidades del mensaje actual como si fueran contexto previo.
            candidates = history_candidates

            if not candidates:
                return ContextResolutionResult(
                    has_vague_reference=True,
                    has_status_question=False,
                    resolved_reference=None,
                    candidates=[],
                    confidence="none",
                    reason="no_recent_context",
                    recent_tool_result=recent_tool_result,
                    entities=entities,
                )

            if len(candidates) == 1:
                return ContextResolutionResult(
                    has_vague_reference=True,
                    has_status_question=False,
                    resolved_reference=candidates[0],
                    candidates=candidates,
                    confidence="high",
                    reason="single_recent_reference",
                    recent_tool_result=recent_tool_result,
                    entities=entities,
                )

            return ContextResolutionResult(
                has_vague_reference=True,
                has_status_question=False,
                resolved_reference=None,
                candidates=candidates,
                confidence="ambiguous",
                reason="multiple_recent_references",
                recent_tool_result=recent_tool_result,
                entities=entities,
            )

        return ContextResolutionResult(
            has_vague_reference=False,
            has_status_question=False,
            resolved_reference=None,
            candidates=all_candidates,
            confidence="low" if all_candidates else "none",
            reason="context_analysed",
            recent_tool_result=recent_tool_result,
            entities=entities,
        )

    def _has_status_question(self, text: str) -> bool:
        normalized = self._normalized_text(text)
        return any(
            re.search(pattern, normalized, re.I)
            for pattern in self._status_question_patterns
        )

    def _has_vague_reference(self, text: str) -> bool:
        normalized = self._normalized_text(text)
        return any(
            re.search(pattern, normalized, re.I)
            for pattern in self._vague_reference_patterns
        )

    def _extract_history_entities(self, context: ContextPackage) -> list[ContextEntity]:
        entities: list[ContextEntity] = []

        for reverse_index, turn in enumerate(reversed(context.recent_history)):
            index = len(context.recent_history) - 1 - reverse_index

            # Regla importante:
            # - El usuario declara contexto.
            # - Las tools aportan evidencia.
            # - El assistant NO debe crear nuevas pattern entities, porque sus preguntas
            #   pueden contaminar el contexto con frases como "editar un archivo existente"
            #   o sugerencias secundarias como "Google Workspace".
            include_pattern_entities = turn.role in {"user", "tool"}

            entities.extend(
                self._extract_entities_from_text(
                    turn.content,
                    turn.role,
                    index,
                    include_pattern_entities=include_pattern_entities,
                    include_known_fallback=turn.role in {"user", "tool"},
                )
            )

            if turn.role == "tool":
                tool_result = self._parse_tool_result(turn.content)
                if tool_result is not None:
                    entities.extend(
                        self._entities_from_tool_result(tool_result, turn.role, index)
                    )

        return entities

    def _extract_current_entities(self, context: ContextPackage) -> list[ContextEntity]:
        return self._extract_entities_from_text(
            context.user_message,
            "user",
            len(context.recent_history),
            include_pattern_entities=True,
        )

    def _extract_entities_from_text(
        self,
        text: str,
        source_role: str,
        history_index: int,
        *,
        include_pattern_entities: bool = True,
        include_known_fallback: bool = True,
    ) -> list[ContextEntity]:
        entities: list[ContextEntity] = []

        if include_pattern_entities:
            entities.extend(
                self._extract_pattern_entities_from_text(
                    text,
                    source_role,
                    history_index,
                )
            )

        entities.extend(self._extract_url_entities(text, source_role, history_index))
        entities.extend(self._extract_file_entities(text, source_role, history_index))
        if include_known_fallback:
            entities.extend(
                self._extract_known_fallback_entities(text, source_role, history_index)
            )

        return self._dedupe_entities(entities)

    def _extract_pattern_entities_from_text(
        self,
        text: str,
        source_role: str,
        history_index: int,
    ) -> list[ContextEntity]:
        entities: list[ContextEntity] = []

        # Declaraciones abiertas:
        # "vamos a trabajar con X", "trabajaremos con X", "estamos trabajando en X"
        declaration_patterns = (
            r"\b(?:vamos\s+a\s+)?trabajar(?:emos)?\s+(?:con|en)\s+(.+)$",
            r"\bestamos\s+trabajando\s+(?:con|en)\s+(.+)$",
            r"\btrabajaremos\s+(?:con|en)\s+(.+)$",
            r"\bvamos\s+a\s+revisar\s+(.+)$",
            r"\bquiero\s+usar\s+(.+?)(?:\s+ahora|\s+despu[eé]s|\s+hoy|$)",
            r"\busaremos\s+(.+)$",
        )

        # Roles explícitos:
        # "la app será X", "el editor será X", "la plataforma es X"
        role_patterns = (
            r"\b(?:la|el)\s+(?:app|aplicaci[oó]n|herramienta|plataforma|editor|programa|software)\s+(?:ser[aá]|es|seria|sería)\s+(.+)$",
            r"\b(?:app|aplicaci[oó]n|herramienta|plataforma|editor|programa|software)\s*:\s*(.+)$",
        )

        # Opciones múltiples:
        # "podemos usar X o Y", "tengo dos opciones: X y Y"
        option_patterns = (
            r"\b(?:podemos|puedo|podr[ií]amos)\s+usar\s+(.+)$",
            r"\b(?:tengo|tenemos)\s+(?:dos|varias)?\s*opciones\s*:?\s*(.+)$",
            r"\b(?:las|mis|nuestras)?\s*opciones\s+(?:son|ser[ií]an)\s+(.+)$",
        )

        # Archivos o piezas de trabajo:
        # "el archivo principal es X", "el error está en X"
        work_item_patterns = (
            r"\b(?:el|la)\s+(?:archivo|documento|error|problema|fallo|script|m[oó]dulo|clase|funci[oó]n|vista|componente)\s+(?:principal\s+)?(?:es|ser[aá]|est[aá]\s+en|parece\s+estar\s+en)\s+(.+)$",
            r"\b(?:tenemos|tengo)\s+(.+\.(?:py|json|md|txt|yaml|yml|pdf|png|jpg|jpeg|csv|xlsx)(?:\s*(?:,|y|o)\s*.+)?)$",
        )

        # Plataformas explícitas en instrucciones de contenido:
        # "monta ese texto en X", "pasa este copy a X"
        platform_patterns = (
            r"\b(?:monta|montar|pon|poner|usa|usar|pasa|pasar|coloca|colocar|mete|meter|agrega|agregar|añade|a[nñ]adir)\b.+?\b(?:en|a|para|dentro\s+de)\s+(.+)$",
            r"\b(?:haz|hacer|crea|crear|diseña|dise[ñn]ar)\b.+?\b(?:en|con|para)\s+(.+)$",
        )

        for pattern in (
            *declaration_patterns,
            *role_patterns,
            *option_patterns,
            *work_item_patterns,
            *platform_patterns,
        ):
            for match in re.finditer(pattern, text, re.I):
                raw = match.group(1)
                for value in self._split_entity_list(raw):
                    cleaned = self._clean_entity_candidate(value)
                    if not cleaned:
                        continue
                    entities.append(
                        ContextEntity(
                            value=cleaned,
                            kind=self._infer_entity_kind(cleaned),
                            source_role=source_role,
                            history_index=history_index,
                            confidence="high",
                            metadata={"source": "pattern"},
                        )
                    )

        return entities

    def _extract_url_entities(
        self,
        text: str,
        source_role: str,
        history_index: int,
    ) -> list[ContextEntity]:
        entities: list[ContextEntity] = []
        for match in re.finditer(r"https?://[^\s\"')>]+", text, re.I):
            value = match.group(0).rstrip(".,)")
            entities.append(
                ContextEntity(
                    value=value,
                    kind="url",
                    source_role=source_role,
                    history_index=history_index,
                    confidence="high",
                )
            )
        return entities

    def _extract_file_entities(
        self,
        text: str,
        source_role: str,
        history_index: int,
    ) -> list[ContextEntity]:
        entities: list[ContextEntity] = []
        for match in re.finditer(
            r"\b[\w.-]+\.(?:py|json|md|txt|yaml|yml|pdf|png|jpg|jpeg|csv|xlsx)\b",
            text,
            re.I,
        ):
            entities.append(
                ContextEntity(
                    value=match.group(0),
                    kind="file",
                    source_role=source_role,
                    history_index=history_index,
                    confidence="high",
                )
            )
        return entities

    def _extract_known_fallback_entities(
        self,
        text: str,
        source_role: str,
        history_index: int,
    ) -> list[ContextEntity]:
        normalized = self._normalized_text(text)
        entities: list[ContextEntity] = []

        for site in self._known_sites:
            if self._contains_word(normalized, site.lower()):
                entities.append(
                    ContextEntity(
                        value=site,
                        kind="site",
                        source_role=source_role,
                        history_index=history_index,
                        confidence="medium",
                        metadata={"source": "known_fallback"},
                    )
                )

        for app in self._known_apps:
            if self._contains_word(normalized, app.lower()):
                entities.append(
                    ContextEntity(
                        value=app,
                        kind="app",
                        source_role=source_role,
                        history_index=history_index,
                        confidence="medium",
                        metadata={"source": "known_fallback"},
                    )
                )

        return entities

    def _entities_from_tool_result(
        self,
        tool_result: dict[str, Any],
        source_role: str,
        history_index: int,
    ) -> list[ContextEntity]:
        entities: list[ContextEntity] = []

        tool_name = str(tool_result.get("tool_name", "tool_result"))
        entities.append(
            ContextEntity(
                value=tool_name,
                kind="tool_result",
                source_role=source_role,
                history_index=history_index,
                confidence="high",
                metadata=tool_result,
            )
        )

        data = tool_result.get("data")
        if isinstance(data, dict):
            for key in ("url", "query", "app_name", "target", "file", "path", "action"):
                value = data.get(key)
                if not value or not isinstance(value, str):
                    continue
                cleaned = self._clean_entity_candidate(value)
                if not cleaned:
                    continue
                entities.append(
                    ContextEntity(
                        value=cleaned,
                        kind=self._infer_entity_kind(cleaned),
                        source_role=source_role,
                        history_index=history_index,
                        confidence="high",
                        metadata={"source": "tool_result_data", "key": key},
                    )
                )

        return entities

    def _recent_tool_result(self, context: ContextPackage) -> dict[str, Any] | None:
        for turn in reversed(context.recent_history):
            if turn.role != "tool":
                continue
            tool_result = self._parse_tool_result(turn.content)
            if tool_result is None:
                continue
            keys = {"tool_name", "success", "data", "metadata"}
            if keys & tool_result.keys():
                return tool_result
        return None

    def _parse_tool_result(self, content: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(content)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _has_content_transfer_intent(self, text: str) -> bool:
        patterns = (
            r"\bmont(a|ar|arlo|arla|alo|ala)\b",
            r"\bpon(er|lo|la)?\b",
            r"\busa(r|lo|la)?\b",
            r"\bpas(a|ar|arlo|arla)\b",
            r"\bcoloc(a|ar|arlo|arla)\b",
            r"\bmete(r|lo|la)?\b",
            r"\bagreg(a|ar|alo|ala)\b",
            r"\ba[nñ]ad(e|ir|elo|ela)\b",
            r"\bcrea(r)?\b",
            r"\bdise[nñ](a|ar)\b",
        )
        return any(re.search(pattern, text, re.I) for pattern in patterns)

    def _has_vague_content_object(self, text: str) -> bool:
        patterns = (
            r"\bes[eo]s?\s+(texto|contenido|copy|idea|informaci[oó]n|imagen|foto|archivo|material|dise[nñ]o)\b",
            r"\best[eo]s?\s+(texto|contenido|copy|idea|informaci[oó]n|imagen|foto|archivo|material|dise[nñ]o)\b",
            r"\b(el|la)\s+(texto|contenido|copy|idea|informaci[oó]n|imagen|foto|archivo|material|dise[nñ]o)\b",
            r"\besto\b",
            r"\beso\b",
        )
        return any(re.search(pattern, text, re.I) for pattern in patterns)

    def _explicit_platforms_in_current_message(self, text: str) -> list[str]:
        platforms: list[str] = []

        # Fallback conocido.
        normalized = self._normalized_text(text)
        for platform in self._known_sites + self._known_apps:
            if self._contains_word(normalized, platform.lower()):
                platforms.append(platform)

        # Plataforma abierta después de preposiciones típicas.
        for pattern in (
            r"\b(?:en|a|para|dentro\s+de)\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.-]*){0,3})\b",
            r"\b(?:en|a|para|dentro\s+de)\s+([a-záéíóúñ][\wáéíóúñ.-]*(?:\s+[a-záéíóúñ][\wáéíóúñ.-]*){0,3})\b",
        ):
            for match in re.finditer(pattern, text):
                cleaned = self._clean_entity_candidate(match.group(1))
                if cleaned:
                    platforms.append(cleaned)

        return self._dedupe_candidates(platforms)

    def _split_entity_list(self, raw: str) -> list[str]:
        text = raw.strip()

        # Cortar explicaciones posteriores, no parte de la entidad.
        text = re.split(
            r"\s+(?:para|porque|cuando|mientras|despu[eé]s|ahora|hoy)\b",
            text,
            maxsplit=1,
            flags=re.I,
        )[0]

        text = text.strip(" .,:;!?¿¡()[]{}\"'`")

        if not text:
            return []

        # Si contiene archivos, devolver archivos directamente.
        files = re.findall(
            r"\b[\w.-]+\.(?:py|json|md|txt|yaml|yml|pdf|png|jpg|jpeg|csv|xlsx)\b",
            text,
            re.I,
        )
        if files:
            return files

        parts = re.split(r"\s*(?:,|/|\bo\b|\by\b|\bor\b|\band\b)\s*", text, flags=re.I)
        return [part for part in parts if part.strip()]

    def _clean_entity_candidate(self, value: str) -> str | None:
        cleaned = (value or "").strip()
        cleaned = cleaned.strip(" .,:;!?¿¡()[]{}\"'`")

        # Quitar prefijos conversacionales comunes.
        cleaned = re.sub(
            r"^(?:la|el|los|las|un|una|mi|mis|tu|tus|nuestro|nuestra)\s+",
            "",
            cleaned,
            flags=re.I,
        ).strip()

        # Cortar frases largas genéricas.
        cleaned = re.split(
            r"\s+(?:para|porque|cuando|mientras|despu[eé]s|ahora|hoy)\b",
            cleaned,
            maxsplit=1,
            flags=re.I,
        )[0].strip()

        normalized = self._normalized_text(cleaned)
        if normalized in self._entity_stopwords:
            return None

        if len(cleaned) > 80:
            return None

        # Evitar capturas claramente verbales o preguntas completas.
        if re.search(r"\b(quieres|necesitas|puedes|debo|hacer|realizar)\b", normalized):
            return None

        # Evitar entidades demasiado largas salvo archivos/URLs.
        if not self._looks_like_file(cleaned) and not self._looks_like_url(cleaned):
            if len(cleaned.split()) > 5:
                return None

        return cleaned or None

    def _infer_entity_kind(self, value: str) -> str:
        if self._looks_like_url(value):
            return "url"
        if self._looks_like_file(value):
            return "file"
        return "entity"

    def _looks_like_url(self, value: str) -> bool:
        return bool(re.match(r"https?://", value or "", re.I))

    def _looks_like_file(self, value: str) -> bool:
        return bool(
            re.search(
                r"\.(?:py|json|md|txt|yaml|yml|pdf|png|jpg|jpeg|csv|xlsx)$",
                value or "",
                re.I,
            )
        )

    def _dedupe_entities(self, entities: list[ContextEntity]) -> list[ContextEntity]:
        deduped: list[ContextEntity] = []
        seen: set[str] = set()
        for entity in entities:
            key = self._normalized_text(entity.value)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(entity)
        return deduped

    def _dedupe_candidates(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = self._normalized_text(value)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(value)
        return deduped

    def _contains_word(self, text: str, phrase: str) -> bool:
        escaped = re.escape(self._normalized_text(phrase))
        return bool(re.search(rf"(?<!\w){escaped}(?!\w)", text))

    def _normalized_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())
