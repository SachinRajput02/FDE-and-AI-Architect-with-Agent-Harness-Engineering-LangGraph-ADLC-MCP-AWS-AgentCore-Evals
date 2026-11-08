import { useEffect, useState } from "react";
import { ClaimPage } from "./ClaimPage";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

function currentRoute(): string {
  return window.location.hash.replace(/^#/, "") || "/";
}

function Page({ route }: Readonly<{ route: string }>) {
  const claim = /^\/claims\/([\w-]+)$/.exec(route);
  if (claim?.[1]) return <ClaimPage claimId={claim[1]} />;
  if (route === "/instructions") return <Instructions />;
  return <Queue />;
}

export function App() {
  const [route, setRoute] = useState(currentRoute);

  useEffect(() => {
    const update = () => {
      setRoute(currentRoute());
    };
    window.addEventListener("hashchange", update);
    return () => {
      window.removeEventListener("hashchange", update);
    };
  }, []);

  return (
    <>
      <header className="top">
        <a href="#/" className="brand">
          UnderCover <span className="tagline">Claims</span>
        </a>
        <nav>
          <a href="#/">Queue</a>
          <a href="#/instructions">Agent instructions</a>
        </nav>
      </header>
      <main>
        <Page key={route} route={route} />
      </main>
    </>
  );
}
