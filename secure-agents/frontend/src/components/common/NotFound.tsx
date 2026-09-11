import { Link } from "@tanstack/react-router";
import { Button } from "@carbon/react";
const NotFound = () => {
  return (
    <div className="mx-auto flex h-screen max-w-sm flex-col items-center justify-center text-center">
      <h1 className="text-primary mb-4 text-8xl font-bold leading-none">404</h1>
      <p className="text-md">Oops!</p>
      <p className="text-md">Page not found.</p>
      <Link to="/">
        <Button className="mt-4">Go back</Button>
      </Link>
    </div>
  );
};

export default NotFound;
