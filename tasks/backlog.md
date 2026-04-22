# Backlog — Lumina Ant

Tareas pendientes del proyecto. Actualizar junto con `todo.md` (completadas) y `lessons.md` (lecciones).

---

## 🔴 Alta prioridad

_(vacío por ahora)_

---

## 🟡 Media prioridad

- [x] **Prompt caching para el esquema de BD** — ✅ implementado
- [x] **Filtrar esquema enviado al copiloto IA** — ✅ ya implementado: `DB_SCHEMA` en `chat_service.py` solo incluye `ventas`, `gastos`, `inventario`, `clientes`. Las tablas de infraestructura (`watched_files`, `column_mappings`, `alert_configs`, `users`, `user_configs`) ya estaban excluidas. `alertas` se decidió no incluir (edge case, la UI ya las muestra, `detalles` es JSON serializado que confunde al modelo).
- [x] **Tests del frontend** — ✅ implementado (Chat.test.jsx, ChatMessage.test.jsx, AuthContext.test.jsx)
- [x] **Gráficas en el chat** — ✅ implementado: ChatMessage.jsx detecta tablas markdown en la respuesta IA y ofrece toggle "Ver gráfica" con Recharts (BarChart / LineChart según heurística de columnas)
- [ ] **Chat persistente** — 🔲 pendiente. Historial de conversaciones guardado en BD por usuario. Requiere: modelo `ChatConversation` en models.py, endpoints GET/POST/DELETE `/api/chat/history`, y actualización de Chat.jsx para cargar desde API en lugar de localStorage.

---

## 🟢 Baja / ideas

_(vacío por ahora)_

---

## ✅ Completadas (pendiente de archivar en todo.md)

_(mover aquí antes de registrar en todo.md)_
