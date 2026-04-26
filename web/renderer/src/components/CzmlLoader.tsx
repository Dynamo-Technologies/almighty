import { CzmlDataSource } from "resium";

type CzmlLoaderProps = {
  url: string;
};

/**
 * Mounts a Resium CzmlDataSource for the given URL inside a parent <Viewer>.
 * Switching the URL is handled by remounting via React `key` from the parent
 * so the previous data source unmounts cleanly before the next one loads.
 */
export function CzmlLoader({ url }: CzmlLoaderProps) {
  return <CzmlDataSource data={url} />;
}
