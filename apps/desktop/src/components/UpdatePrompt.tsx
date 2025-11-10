import React from "react";
import { Modal, ModalBody, ModalFooter } from "./ui/Modal";
import { Button } from "./ui/Button";

const UpdatePrompt: React.FC = () => {
  const [updateInfo, setUpdateInfo] = React.useState<any | null>(null);
  const [isUpdating, setIsUpdating] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Dynamically import to avoid build-time resolution issues
        const updater = await import("@tauri-apps/plugin-updater").catch(() => null as any);
        if (!updater?.check) return;
        const result = await updater.check();
        if (!cancelled && result?.available) {
          setUpdateInfo(result);
        }
      } catch (_e) {
        // ignore update check errors
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleUpdateNow = async () => {
    if (!updateInfo?.available) return;
    setIsUpdating(true);
    try {
      await updateInfo.downloadAndInstall();
      // App may restart automatically after install depending on platform/packager.
      // If not, the user can relaunch manually.
    } catch (_e) {
      setIsUpdating(false);
    }
  };

  return (
    <Modal
      isOpen={Boolean(updateInfo?.available)}
      onClose={() => setUpdateInfo(null)}
      title="Update available"
      description={updateInfo?.version ? `Version ${updateInfo.version} is ready to install.` : "A new version is available."}
      size="md"
    >
      <ModalBody>
        <p className="text-sm text-neutral-700 dark:text-neutral-300">
          A newer version of CraftML Studio is available. You can install it now or later. The app will restart after the update.
        </p>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" onClick={() => setUpdateInfo(null)}>
          Later
        </Button>
        <Button variant="primary" onClick={handleUpdateNow} isLoading={isUpdating}>
          Update now
        </Button>
      </ModalFooter>
    </Modal>
  );
};

export default UpdatePrompt;


