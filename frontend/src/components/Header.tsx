import { List, SignOut } from "@phosphor-icons/react";
import type { Usuario } from "../types";

export function Header({
  kicker,
  titulo,
  usuario,
  onCerrarSesion,
  onAbrirMenu,
  acciones,
}: {
  kicker: string;
  titulo: string;
  usuario: Usuario;
  onCerrarSesion: () => void;
  /** Solo se ve en pantallas angostas -en el escritorio el sidebar ya está
   * siempre visible y no hace falta un botón para abrirlo (ver `.hamburger`
   * en index.css, oculto por defecto). */
  onAbrirMenu: () => void;
  acciones?: React.ReactNode;
}) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "17px 22px",
        borderBottom: "1px solid var(--color-border)",
        position: "sticky",
        top: 0,
        background: "var(--color-bg)",
        zIndex: 5,
      }}
    >
      <button
        className="hamburger"
        onClick={onAbrirMenu}
        aria-label="Abrir menú"
        style={{
          background: "transparent",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
          color: "var(--color-text-bright-muted)",
          cursor: "pointer",
          alignItems: "center",
          justifyContent: "center",
          padding: 7,
          flex: "0 0 auto",
        }}
      >
        <List size={15} />
      </button>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="kicker">{kicker}</div>
        <h1 className="screen-title">{titulo}</h1>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          fontSize: 11.5,
          color: "var(--color-text-dim)",
        }}
      >
        <span
          style={{
            maxWidth: 200,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={usuario.correo}
        >
          {usuario.nombre_completo}
        </span>
        <button
          onClick={onCerrarSesion}
          title="Cerrar sesión"
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            color: "var(--color-text-dim)",
            cursor: "pointer",
            display: "grid",
            placeItems: "center",
            padding: 6,
          }}
        >
          <SignOut size={13} />
        </button>
      </div>

      {acciones}
    </header>
  );
}
