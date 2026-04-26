type AccessDeniedProps = {
  required: string;
  actual?: string;
};

export function AccessDenied({ required, actual }: AccessDeniedProps) {
  return (
    <div className="access-denied">
      <h1>ACCESS DENIED</h1>
      <p>This route requires cell role: <strong>{required}</strong></p>
      <p>Your token: {actual ?? "<no token>"}</p>
      <p className="access-denied__hint">
        Append <code>?jwt=&lt;your-token&gt;</code> to the URL to set a token.
      </p>
    </div>
  );
}
