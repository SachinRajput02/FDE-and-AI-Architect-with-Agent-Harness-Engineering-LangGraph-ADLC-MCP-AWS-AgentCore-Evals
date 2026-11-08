import { useJson } from "./useJson";

export function Instructions() {
  const { data, error } = useJson<{ text: string }>("/api/instructions", false);

  if (error)
    return <p role="alert">Could not load the instructions. {error}</p>;
  if (!data) return <p>Loading the instructions</p>;

  return (
    <>
      <h1>Agent instructions</h1>
      <p className="muted">
        The UnderCover Agent works from these instructions. They are read only.
      </p>
      <div className="panel instructions">{data.text}</div>
    </>
  );
}
