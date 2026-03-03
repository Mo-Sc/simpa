% VISUALIZE JEREMIES CUSTOM SENSOR.MASK FOR ITHERA GEOMETRY

clear; close all; clc;

%% --- Initialization ---

dx = 1e-4;                  % grid spacing [m]
grid_dim_y = 15e-3;         % physical grid size in y [m]
Nx = 750;
Ny = 150;
Nz = 800;
n_elem = 256;               % number of detector elements
coverage = 125;             % total angular coverage in degrees
center_of_rotation = [51.2e-3, Ny/2*dx, Nx/2*dx]; % as in the simulation
grid_3D = true;

%% --- Compute the geometry using your colleague's code ---

[sensor_mask, sensor_value, m_theta, m_phi, sensor_cart_coord, sensor_elem_mat] = ...
    ithera_geometry(dx, dx, dx, grid_dim_y, Nx, Ny, Nz, n_elem, coverage, center_of_rotation, grid_3D);

%% --- Analysis: number of grid points per array element ---

found_idxs = zeros(1, n_elem);
for sensor_idx = 1:n_elem
    found_idxs(sensor_idx) = sum(sensor_value(:) == (n_elem - sensor_idx + 1));
end

figure('Color', 'w');
plot(found_idxs, '-o', 'LineWidth', 2, 'MarkerFaceColor', 'b');
xlabel('Detector element index');
ylabel('Number of grid points');
title('Number of grid points per detector element');
grid on;
set(gca, 'FontSize', 12);

%% --- 3D Visualization of the array geometry ---

% Extract all detector points
X = sensor_cart_coord(1, :) * 1e3;  % convert to mm
Y = sensor_cart_coord(2, :) * 1e3;
Z = sensor_cart_coord(3, :) * 1e3;

% Compute element center positions for reference
element_centers = squeeze(mean(sensor_elem_mat, 2))' * 1e3;

figure('Color', 'w');
scatter3(X, Y, Z, 8, 'r', 'filled');
hold on;
scatter3(element_centers(:,1), element_centers(:,2), element_centers(:,3), 40, 'b', 'filled');
plot3(element_centers(:,1), element_centers(:,2), element_centers(:,3), 'k-', 'LineWidth', 1);

xlabel('x [mm]');
ylabel('y [mm]');
zlabel('z [mm]');
title('Custom iThera-style Curved Array Geometry');
axis equal;
grid on;
view(3);
legend({'Sampling points','Element centers'}, 'Location', 'best');
set(gca, 'FontSize', 12);

%% --- Optional: display curvature in 3D ---
% This helps visualize that the array lies on a curved surface.

% Draw a fitted circle/arc through element centers in XZ plane (roughly)
[theta_fit, rho_fit] = cart2pol(element_centers(:,3), element_centers(:,1));
[~, sort_idx] = sort(theta_fit);
plot3(element_centers(sort_idx,1), element_centers(sort_idx,2), element_centers(sort_idx,3), ...
      'g-', 'LineWidth', 1.5);

%% --- Optional: print some info ---
fprintf('Number of detector elements: %d\n', n_elem);
fprintf('Typical points per element: %.1f ± %.1f\n', mean(found_idxs), std(found_idxs));
fprintf('m_theta = %d, m_phi = %d\n', m_theta, m_phi);