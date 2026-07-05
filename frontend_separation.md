# Plan de Separación de Responsabilidades y Módulos Frontend

Este documento detalla la división del desarrollo del frontend de **SharkHub** en tres módulos independientes para que los tres integrantes del grupo trabajen de forma paralela y lo integren fácilmente al final.

---

## 1. Arquitectura General e Integración

Para asegurar una integración sin conflictos, se recomienda usar **Vite + React** (o JavaScript Vanilla estructurado) con la siguiente estrategia:

### A. Almacenamiento de Sesión (Compartido)
El token JWT y el perfil del usuario se guardarán en `localStorage`:
- `token`: El JWT devuelto por el backend (`andres.customer@email.com`).
- `user_role`: El rol del usuario (`customer`, `barber` o `owner`).

### B. Cliente API Común
Todos los participantes usarán el mismo archivo cliente (`api.js`) para realizar las llamadas. Este cliente agrega automáticamente el token JWT en las cabeceras.

```javascript
// api.js - Cliente HTTP Compartido
const BASE_URL = "http://127.0.0.1:8001"; // Puerto de Reglas de Negocio

export async function request(method, path, body = null) {
  const token = localStorage.getItem("token");
  const headers = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const config = {
    method,
    headers,
  };
  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE_URL}${path}`, config);
  
  if (response.status === 401) {
    // Redireccionar a login si el token expira o es inválido
    localStorage.clear();
    window.location.href = "/login";
    return;
  }
  
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Error en la petición");
  }

  if (response.status === 204) return null;
  return response.json();
}
```

---

## 2. División de Módulos (3 Participantes)

---

### 👤 INTEGRANTE 1: Módulo de Autenticación, Landing y Reservas (Customer)
**Responsabilidad:** Landing Page del visitante, registro, inicio de sesión (JWT y Google Login) y flujo completo de reserva de citas para el cliente (`customer`).

#### 🛠️ Vistas / Componentes a Desarrollar:
1. **Landing Page:** Muestra descripción de la barbería, lista de barberos y lista de servicios generales.
2. **Login / Registro:** Formularios tradicionales y botón de "Iniciar sesión con Google".
3. **Panel del Cliente (Dashboard Customer):**
   * Vista de selección de Barbero y Servicio.
   * Calendario interactivo para ver horas disponibles de un barbero.
   * Formulario de confirmación de reserva (añadir notas).
   * Listado de citas agendadas por el cliente.

#### 🔗 Llamados a la API:
* **Registrar Usuario:** `POST /auth/register`
  * Body: `{ "name": "...", "email": "...", "password": "..." }`
* **Login Tradicional:** `POST /auth/login`
  * Body: `{ "email": "...", "password": "..." }`
* **Google OAuth Bridge:** `POST /auth/google`
  * Body: `{ "id_token": "..." }`
* **Obtener Horas Disponibles:** `GET /api/customer/available-times?barber_id={id}&service_id={id}&date={YYYY-MM-DD}`
* **Crear Cita:** `POST /api/customer/appointments`
  * Body: `{ "barber_id": "...", "service_id": "...", "appointment_date": "...", "start_time": "...", "notes": "..." }`
* **Ver mis Citas:** `GET /appointments` (autofiltrado por token para customer).

---

### 💈 INTEGRANTE 2: Módulo del Barbero (Barber Dashboard)
**Responsabilidad:** Gestión de agenda del barbero activo, administración de sus propios servicios y catálogo de productos, y configuración de horarios de disponibilidad.

#### 🛠️ Vistas / Componentes a Desarrollar:
1. **Panel del Barbero (Dashboard Barber):**
   * Vista de la agenda diaria del barbero (lista de citas asignadas).
   * Botones de acción rápida en cada cita: "Aceptar", "Rechazar" o "Cancelar".
2. **Módulo de Servicios Propios:**
   * Formulario para crear/editar servicios (nombre, precio, duración).
   * Lista de servicios con opción de borrar o desactivar.
3. **Módulo de Inventario de Productos:**
   * Formulario de creación/edición de productos (nombre, precio, stock, imagen).
   * Lista de productos.
4. **Módulo de Disponibilidad:**
   * Configuración de horario laboral diario (ej. lunes de 09:00 a 17:00).

#### 🔗 Llamados a la API:
* **Ver Citas del Barbero:** `GET /api/barber/appointments?date={YYYY-MM-DD}`
* **Cambiar Estado de Cita:** `PUT /appointments/{appointment_id}`
  * Body: `{ "status": "confirmed | cancelled" }`
* **Crear/Editar Servicios:** `POST /barbershops/{shop_id}/services` / `PUT /barbershops/{shop_id}/services/{id}`
  * Body: `{ "name": "...", "description": "...", "price": 10.0, "duration_minutes": 30 }`
* **Crear/Editar Productos:** `POST /barbershops/{shop_id}/products` / `PUT /barbershops/{shop_id}/products/{id}`
  * Body: `{ "name": "...", "description": "...", "price": 10.0, "stock": 15, "image_url": "..." }`
* **Definir Disponibilidad:** `POST /barbers/{barber_id}/availabilities`
  * Body: `{ "barbershop_id": "...", "day_of_week": 1, "start_time": "09:00", "end_time": "17:00", "is_available": true }`

---

### 👑 INTEGRANTE 3: Módulo del Propietario (Owner Dashboard)
**Responsabilidad:** Configuración de la barbería, gestión del equipo de barberos (membresías y generación de invitaciones) y supervisión global de citas.

#### 🛠️ Vistas / Componentes a Desarrollar:
1. **Panel del Propietario (Dashboard Owner):**
   * Formulario de edición del perfil de la barbería (nombre, dirección, teléfono, logo).
2. **Gestión de Barberos (Equipo):**
   * Buscador de usuarios para agregar barberos por correo electrónico.
   * Lista de miembros activos en la barbería con opción de cambiar estado ("activo", "inactivo").
   * Generador de códigos de invitación únicos (`SH-XXX-YYY`) con fecha de expiración.
3. **Supervisión de Citas (Consola Global):**
   * Calendario/Lista de todas las citas de la sucursal.
   * Filtro de citas por Barbero y por Fecha.

#### 🔗 Llamados a la API:
* **Actualizar Perfil de Barbería:** `PUT /api/owner/barbershop`
  * Body: `{ "name": "...", "phone": "...", "email": "...", "address": "...", "description": "...", "logo_url": "..." }`
* **Añadir Barbero al Equipo:** `POST /api/owner/barbers`
  * Body: `{ "email": "..." }`
* **Cambiar Estado del Barbero:** `PATCH /api/owner/barbers/{member_id}/status`
  * Body: `{ "status": "active | inactive" }`
* **Generar Código de Invitación:** `POST /barbershops/{shop_id}/invitations`
  * Body: `{ "expires_at": "YYYY-MM-DD HH:MM:SS" }`
* **Listar Citas Globales de la Barbería:** `GET /api/owner/appointments?date={YYYY-MM-DD}&barber_id={id}`

---

## 3. Estrategia de Unión (Merging)
Al finalizar, unir el código será muy sencillo si respetan esta estructura de carpetas:

```text
sharkhub-frontend/
│
├── src/
│   ├── api/
│   │   └── api.js              <-- Cliente API común
│   │
│   ├── components/
│   │   ├── auth/               <-- Código Integrante 1
│   │   ├── customer/           <-- Código Integrante 1
│   │   ├── barber/             <-- Código Integrante 2
│   │   └── owner/              <-- Código Integrante 3
│   │
│   ├── App.jsx                 <-- Enrutador que lee localStorage.getItem("user_role")
│   └── main.jsx
```
