export function Header({
  kicker,
  titulo,
  usuarioId,
  onCambiarUsuarioId,
  acciones,
}: {
  kicker: string;
  titulo: string;
  usuarioId: number;
  onCambiarUsuarioId: (id: number) => void;
  acciones?: React.ReactNode;
}) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        gap: 17,
        padding: "17px 22px",
        borderBottom: "1px solid var(--color-border)",
        position: "sticky",
        top: 0,
        background: "var(--color-bg)",
        zIndex: 5,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="kicker">{kicker}</div>
        <h1 className="screen-title">{titulo}</h1>
      </div>

      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          fontSize: 11,
          color: "var(--color-text-dim)",
        }}
      >
        usuario_id
        <input
          type="number"
          min={1}
          value={usuarioId}
          onChange={(evento) => onCambiarUsuarioId(Number(evento.target.value) || 1)}
          style={{
            width: 56,
            padding: "5px 8px",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            color: "var(--color-text)",
            fontSize: 11.5,
          }}
        />
      </label>

      {acciones}
    </header>
  );
}
