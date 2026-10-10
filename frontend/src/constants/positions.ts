/**
 * Position constants for office elements.
 *
 * All positions are in pixels relative to the canvas origin (top-left).
 */

// ============================================================================
// WALL DECORATIONS
// ============================================================================

/** Employee of the Month frame position */
export const EMPLOYEE_OF_MONTH_POSITION = { x: 184, y: 50 };

/** City window position */
export const CITY_WINDOW_POSITION = { x: 319, y: 30 };

/** Safety sign position */
export const SAFETY_SIGN_POSITION = { x: 1120, y: 40 };

/** Wall clock position */
export const WALL_CLOCK_POSITION = { x: 581, y: 80 };

/** Wall outlet position (below clock) */
export const WALL_OUTLET_POSITION = { x: 581, y: 209 };

/** Whiteboard position */
export const WHITEBOARD_POSITION = { x: 641, y: 11 };

/** Water cooler position */
export const WATER_COOLER_POSITION = { x: 1010, y: 200 };

/** Coffee machine position (to the right of water cooler) */
export const COFFEE_MACHINE_POSITION = { x: 1081, y: 191 };

// ============================================================================
// FLOOR ELEMENTS
// ============================================================================

/** Printer station position (bottom left corner) */
export const PRINTER_STATION_POSITION = { x: 50, y: 945 };

/** Plant position (to the right of printer) */
export const PLANT_POSITION = { x: 118, y: 970 };

// ============================================================================
// BOSS AREA
// ============================================================================

/**
 * Draw scale of the main agent (boss) and its desk, relative to the original
 * claude-office art. The agent is the protagonist, so it is drawn at 2x.
 * Everything placed around the boss (rug, trash can, queue slots, nav-grid
 * obstacles) is derived from this value and BOSS_POSITION.
 */
export const BOSS_SCALE = 2;

/**
 * Boss anchor (body center at the desk). Raised from y=900 so the 2x desk
 * still fits above the bottom edge of the 1024px canvas.
 */
export const BOSS_POSITION = { x: 640, y: 795 };

/** Boss area rug position (centered under boss desk) */
export const BOSS_RUG_POSITION = { x: 640, y: 870 };

/** Boss area rug sprite scale (0.3 at 1x; kept inside the canvas) */
export const BOSS_RUG_SCALE = 0.5;

/** Trash can offset from boss desk position (right of the 2x desk) */
export const TRASH_CAN_OFFSET = { x: 170, y: 180 };

// ============================================================================
// DESK GRID
// ============================================================================

/**
 * Desk grid shape — keep in sync with backend `state_machine.py`
 * `StateMachine.DESKS_PER_ROW` / `StateMachine.MIN_DESK_COUNT`.
 * A shared cross-component source is intentionally out of scope; update both
 * sides together when changing the desk grid.
 */
export const DESKS_PER_ROW = 4;
export const MIN_DESK_COUNT = 8;
