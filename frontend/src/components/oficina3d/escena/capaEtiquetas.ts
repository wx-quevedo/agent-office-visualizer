// Fixed DOM container for the drei <Html> labels of the agents.
//
// Without it, drei uses the canvas parent, which can change while the scene
// mounts; drei then creates a new React root on the same element and the
// deferred unmount of the old root wipes the label ("Attempted to
// synchronously unmount a root while React was already rendering"). The
// container is set by Escena3D before the canvas children mount.
export const capaEtiquetas: { current: HTMLElement } = {
  current: null as unknown as HTMLElement,
};
