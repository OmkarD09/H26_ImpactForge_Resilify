/**
 * Resilify Developer Workstation — Frontend Application Controller
 * High-performance, zero-dependency vanilla JS architecture.
 * Supports multi-project adaptability (LinkWatch & SwasthyaVaani).
 */

(function () {
  'use strict';

  // Global State
  const state = {
    currentView: 'overview',
    currentProject: localStorage.getItem('resilify-active-project') || 'linkwatch',
    projectsList: [],
    overviewData: null,
    inventoryData: null,
    workbenchData: null,
    runsData: null,
    capsulesData: null,
    settingsData: null,
    selectedWorkbenchPkg: null,
    inventoryFilters: {
      search: '',
      risk: 'ALL',
      manifest: 'ALL'
    }
  };

  // DOM Elements
  const DOM = {
    viewSections: document.querySelectorAll('.view-section'),
    navLinks: document.querySelectorAll('.sidebar-nav .nav-link'),
    projectSelect: document.getElementById('project-select'),
    sidebarProjectBadge: document.getElementById('sidebar-project-badge'),
    sidebarRepoLabel: document.getElementById('sidebar-repo-label'),
    sidebarRepoName: document.getElementById('sidebar-repo-name'),
    sidebarCommitPill: document.getElementById('sidebar-commit-pill'),
    sidebarDepCount: document.getElementById('sidebar-dep-count'),
    sidebarProposalCount: document.getElementById('sidebar-proposal-count'),
    topbarProjectName: document.getElementById('topbar-project-name'),
    topbarTitle: document.getElementById('topbar-view-title'),
    topbarSnapshotBadge: document.getElementById('topbar-snapshot-badge'),
    topbarSnapshotText: document.getElementById('topbar-snapshot-text'),
    topbarRiskCount: document.getElementById('topbar-risk-count'),
    topbarBaselineStatus: document.getElementById('topbar-baseline-status'),
    btnRunTests: document.getElementById('btn-run-tests'),
    runTestsBtnText: document.getElementById('run-tests-btn-text'),
    btnAnalyze: document.getElementById('btn-analyze-repo'),
    analyzeBtnText: document.getElementById('analyze-btn-text'),
    btnThemeToggle: document.getElementById('btn-theme-toggle'),
    themeBtnLabel: document.getElementById('theme-btn-label'),
    mobileToggleBtn: document.getElementById('mobile-toggle-btn'),
    sidebar: document.getElementById('sidebar'),
    drawerBackdrop: document.getElementById('drawer-backdrop'),
    drawerPanel: document.getElementById('drawer-panel'),
    drawerCloseBtn: document.getElementById('drawer-close-btn'),
    drawerPkgName: document.getElementById('drawer-pkg-name'),
    drawerPkgBadge: document.getElementById('drawer-pkg-badge'),
    drawerContent: document.getElementById('drawer-content'),
    toastContainer: document.getElementById('toast-container'),
    // Overview elements
    ovTotalDeps: document.getElementById('ov-metric-total-deps'),
    ovRisks: document.getElementById('ov-metric-risks'),
    ovProposals: document.getElementById('ov-metric-proposals'),
    ovTests: document.getElementById('ov-metric-tests'),
    ovPriorityTbody: document.getElementById('overview-priority-tbody'),
    ovPriorityCount: document.getElementById('ov-priority-count'),
    ovActivityList: document.getElementById('ov-activity-list'),
    // Inventory elements
    invSearchInput: document.getElementById('inv-search-input'),
    invRiskSelect: document.getElementById('inv-risk-select'),
    invManifestSelect: document.getElementById('inv-manifest-select'),
    invResetBtn: document.getElementById('inv-reset-btn'),
    invTbody: document.getElementById('inventory-tbody'),
    // Workbench elements
    wbPkgBar: document.getElementById('workbench-pkg-bar'),
    wbPkgTitle: document.getElementById('wb-pkg-title'),
    wbReplacementTitle: document.getElementById('wb-replacement-title'),
    wbActionBadge: document.getElementById('wb-action-badge'),
    wbFeasibilityBadge: document.getElementById('wb-feasibility-badge'),
    wbEvidenceDecls: document.getElementById('wb-evidence-decls'),
    wbEvidenceAst: document.getElementById('wb-evidence-ast'),
    wbEvidencePypi: document.getElementById('wb-evidence-pypi'),
    wbEvidenceBaseline: document.getElementById('wb-evidence-baseline'),
    wbRationaleText: document.getElementById('wb-rationale-text'),
    wbStepsList: document.getElementById('wb-steps-list'),
    wbGapsText: document.getElementById('wb-gaps-text'),
    wbDiffContent: document.getElementById('wb-diff-content'),
    wbCopyDiffBtn: document.getElementById('wb-copy-diff-btn'),
    // Runs elements
    runsProjectNameDisplay: document.getElementById('runs-project-name-display'),
    runsCommandDisplay: document.getElementById('runs-command-display'),
    btnRunsExecuteNow: document.getElementById('btn-runs-execute-now'),
    runsExecuteBtnText: document.getElementById('runs-execute-btn-text'),
    runsCardsContainer: document.getElementById('runs-cards-container'),
    // Settings elements
    settingsTargetPath: document.getElementById('settings-target-path'),
    settingsUpstreamCommit: document.getElementById('settings-upstream-commit'),
    settingsPypiCache: document.getElementById('settings-pypi-cache')
  };

  // Helper: Toast Notifications
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--semantic-green)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--semantic-red)" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    } else {
      iconSvg = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--semantic-violet)" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }
    toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
    DOM.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      toast.style.transition = 'all 0.2s ease';
      setTimeout(() => toast.remove(), 200);
    }, 3400);
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Get severity badge class
  function getSeverityBadge(severity) {
    const s = String(severity || '').toUpperCase();
    if (s === 'CRITICAL') return 'badge badge-red';
    if (s === 'HIGH') return 'badge badge-amber';
    if (s === 'MEDIUM') return 'badge badge-violet';
    if (s === 'LOW') return 'badge badge-neutral';
    if (s === 'SAFE') return 'badge badge-green';
    return 'badge badge-neutral';
  }

  // Router: Hash Navigation
  function navigateTo(hash) {
    const raw = (hash || window.location.hash || '#overview').replace(/^#/, '');
    const [viewName, queryString] = raw.split('?');
    const validViews = ['overview', 'inventory', 'workbench', 'runs', 'capsules', 'settings'];
    const activeView = validViews.includes(viewName) ? viewName : 'overview';

    state.currentView = activeView;

    // Handle query params (e.g. ?pkg=toml)
    if (queryString) {
      const params = new URLSearchParams(queryString);
      const pkgParam = params.get('pkg');
      if (pkgParam) {
        state.selectedWorkbenchPkg = pkgParam;
      }
    }

    // Switch view sections
    DOM.viewSections.forEach(sec => {
      if (sec.id === `view-${activeView}`) {
        sec.classList.add('active-view');
      } else {
        sec.classList.remove('active-view');
      }
    });

    // Update active nav link
    DOM.navLinks.forEach(link => {
      const href = link.getAttribute('href').replace(/^#/, '');
      if (href === activeView) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    // Update Topbar Title
    const titleMap = {
      overview: 'Overview Dashboard',
      inventory: 'Dependency Inventory',
      workbench: 'Migration Workbench',
      runs: 'Verification Runs',
      capsules: 'Dependency Exit Capsules',
      settings: 'Settings & Model Configuration'
    };
    DOM.topbarTitle.textContent = titleMap[activeView] || 'Overview';

    // Close mobile sidebar if open
    DOM.sidebar.classList.remove('mobile-open');

    // Trigger view-specific loads
    if (activeView === 'overview') loadOverview();
    if (activeView === 'inventory') loadInventory();
    if (activeView === 'workbench') loadWorkbench(state.selectedWorkbenchPkg);
    if (activeView === 'runs') loadRuns();
    if (activeView === 'capsules') loadCapsules();
    if (activeView === 'settings') loadSettings();
  }

  // API Call Wrapper with Project Parameter Injected
  async function apiFetch(endpoint) {
    try {
      const sep = endpoint.includes('?') ? '&' : '?';
      const url = `${endpoint}${sep}project=${encodeURIComponent(state.currentProject)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    } catch (err) {
      console.error(`Failed to fetch ${endpoint}:`, err);
      showToast(`Error loading ${endpoint}`, 'error');
      return null;
    }
  }

  // =========================================================================
  // Project Management & Switching
  // =========================================================================
  async function loadProjects() {
    try {
      const res = await fetch('/api/projects');
      if (!res.ok) return;
      const projects = await res.json();
      state.projectsList = projects;

      if (DOM.projectSelect) {
        DOM.projectSelect.innerHTML = '';
        projects.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.id;
          opt.textContent = p.display_name;
          if (p.id === state.currentProject) {
            opt.selected = true;
          }
          DOM.projectSelect.appendChild(opt);
        });
        DOM.projectSelect.value = state.currentProject;
      }
    } catch (e) {
      console.error('Could not fetch projects:', e);
    }
  }

  function handleProjectChange(newProjectId) {
    if (!newProjectId || newProjectId === state.currentProject) return;
    state.currentProject = newProjectId;
    localStorage.setItem('resilify-active-project', newProjectId);

    // Clear caches
    state.overviewData = null;
    state.inventoryData = null;
    state.workbenchData = null;
    state.runsData = null;
    state.capsulesData = null;
    state.settingsData = null;
    state.selectedWorkbenchPkg = null;

    const label = newProjectId === 'swasthyavaani' ? 'SwasthyaVaani (Clinical Platform)' : 'LinkWatch (Track 1 Target)';
    showToast(`Switched active project to ${label}`, 'info');

    // Reload active view
    navigateTo(state.currentView);
  }

  // =========================================================================
  // View 1: Overview
  // =========================================================================
  async function loadOverview() {
    const data = await apiFetch('/api/overview');
    if (!data) return;
    state.overviewData = data;

    // Update Repository & Project Sidebar Info
    if (DOM.sidebarRepoLabel) {
      DOM.sidebarRepoLabel.textContent = data.repository.full_name || data.repository.name;
    }
    if (DOM.sidebarCommitPill) {
      DOM.sidebarCommitPill.textContent = `${data.repository.branch} @ ${data.repository.commit_sha.substring(0, 7)}`;
    }
    if (DOM.sidebarProjectBadge) {
      DOM.sidebarProjectBadge.textContent = state.currentProject === 'swasthyavaani' ? 'Clinical Platform' : 'Track 1 Target';
    }
    if (DOM.topbarProjectName) {
      DOM.topbarProjectName.textContent = data.repository.name;
    }
    if (DOM.topbarSnapshotText) {
      DOM.topbarSnapshotText.textContent = state.currentProject === 'swasthyavaani' ? 'Live Clinical EHR Platform' : 'Track 1 Target Snapshot';
    }

    // Sidebar counts
    if (DOM.sidebarDepCount) DOM.sidebarDepCount.textContent = data.metrics.total_dependencies;
    if (DOM.sidebarProposalCount) DOM.sidebarProposalCount.textContent = data.metrics.generated_proposals;

    // Metric counts
    DOM.ovTotalDeps.textContent = data.metrics.total_dependencies;
    DOM.ovRisks.textContent = data.metrics.actionable_risks;
    DOM.ovProposals.textContent = data.metrics.generated_proposals;
    // Update Header and Card Titles
    const ovRepoDesc = document.getElementById('ov-repo-name-display');
    if (ovRepoDesc) ovRepoDesc.textContent = data.repository.full_name || data.repository.name;

    const ovTestIcon = document.getElementById('ov-test-metric-icon');
    const ovTestBadge = document.getElementById('ov-test-metric-badge');
    const ovTestSub = document.getElementById('ov-metric-tests-sub');

    const isFail = data.metrics.baseline_tests.failed > 0;
    if (DOM.ovTests) {
      DOM.ovTests.textContent = `${data.metrics.baseline_tests.passed} / ${data.metrics.baseline_tests.failed}`;
      DOM.ovTests.style.color = isFail ? 'var(--semantic-red)' : 'var(--semantic-green)';
    }
    if (ovTestBadge) {
      ovTestBadge.className = isFail ? 'badge badge-red' : 'badge badge-green';
      ovTestBadge.textContent = isFail ? `Exit Code ${data.metrics.baseline_tests.exit_code}` : 'Exit Code 0';
    }
    if (ovTestIcon) {
      ovTestIcon.style.color = isFail ? 'var(--semantic-red)' : 'var(--semantic-green)';
    }
    if (ovTestSub) {
      ovTestSub.textContent = isFail
        ? 'Jinja2 & MarkupSafe Incompatibility'
        : 'All Safety Guardrails Passed';
    }

    const ovConflictRow = document.getElementById('ov-conflict-row');
    if (ovConflictRow) {
      if (data.metrics.manifest_conflicts > 0) {
        ovConflictRow.innerHTML = `
          <span class="badge badge-red">pydantic</span>
          <code>==1.10.13</code> in requirements.txt vs <code>&gt;=2</code> in pyproject.toml
        `;
      } else {
        ovConflictRow.innerHTML = `
          <span class="badge badge-green">0 Conflicts</span>
          <code>All manifest versions aligned</code>
        `;
      }
    }

    const ovBaselineRow = document.getElementById('ov-baseline-row');
    if (ovBaselineRow) {
      ovBaselineRow.textContent = `${data.metrics.baseline_tests.total} collected: ${data.metrics.baseline_tests.passed} passed, ${data.metrics.baseline_tests.failed} failed (${data.metrics.baseline_tests.duration_seconds}s)`;
    }

    const ovFailureRow = document.getElementById('ov-failure-row');
    if (ovFailureRow) {
      if (isFail) {
        ovFailureRow.style.color = 'var(--semantic-red)';
        ovFailureRow.innerHTML = `<code>test_report_renders_all_sites</code> &mdash; MarkupSafe soft_unicode`;
      } else {
        ovFailureRow.style.color = 'var(--semantic-green)';
        ovFailureRow.innerHTML = `<span>None &mdash; Clean Passing Test Suite</span>`;
      }
    }

    DOM.topbarRiskCount.textContent = data.metrics.actionable_risks;
    DOM.topbarBaselineStatus.textContent = data.metrics.baseline_tests.failed > 0
      ? `${data.metrics.baseline_tests.passed} / ${data.metrics.baseline_tests.failed} Fail`
      : `${data.metrics.baseline_tests.passed} Passed`;

    // Priority Table
    DOM.ovPriorityCount.textContent = `${data.priority_items.length} Action Items`;
    DOM.ovPriorityTbody.innerHTML = '';

    data.priority_items.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="pkg-cell">
          <span class="pkg-name">${escapeHtml(item.package_name)}</span>
          ${item.baseline_failure ? '<span class="badge badge-red" title="Causes baseline test failure">Baseline Crash</span>' : ''}
        </td>
        <td>
          <span class="${getSeverityBadge(item.severity)}">${escapeHtml(item.severity)}</span>
        </td>
        <td style="max-width: 320px; font-size: 12px; color: var(--text-secondary);">
          ${escapeHtml(item.summary)}
        </td>
        <td>
          <span class="badge badge-violet">${escapeHtml(item.target_action)}</span>
        </td>
        <td style="font-family: var(--font-mono); font-size: 12px;">
          ${item.recommended_package && item.recommended_package !== 'None' ? escapeHtml(item.recommended_package) : '<span style="color: var(--text-muted);">&mdash;</span>'}
        </td>
        <td>
          <button class="btn-secondary btn-open-wb" data-pkg="${escapeHtml(item.package_name)}">
            Workbench &rarr;
          </button>
        </td>
      `;
      DOM.ovPriorityTbody.appendChild(tr);
    });

    // Wire open workbench buttons
    DOM.ovPriorityTbody.querySelectorAll('.btn-open-wb').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const pkg = e.currentTarget.getAttribute('data-pkg');
        window.location.hash = `workbench?pkg=${encodeURIComponent(pkg)}`;
      });
    });

    // Render Recent Activity Timeline
    if (DOM.ovActivityList && data.recent_activity) {
      DOM.ovActivityList.innerHTML = '';
      data.recent_activity.forEach(act => {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        let badgeClass = 'badge-neutral';
        if (act.status === 'VERIFIED_SUCCESS' || act.status === 'SUCCESS') badgeClass = 'badge-green';
        if (act.status === 'FAILED') badgeClass = 'badge-red';
        if (act.status === 'VIOLET_AI') badgeClass = 'badge-violet';

        item.innerHTML = `
          <div class="timeline-dot"></div>
          <div class="timeline-content">
            <div class="timeline-header">
              <span class="timeline-title">${escapeHtml(act.title)}</span>
              <span class="badge ${badgeClass}">${escapeHtml(act.status)}</span>
            </div>
            <p class="timeline-desc">${escapeHtml(act.description)}</p>
            <div class="timeline-meta">
              <span>${escapeHtml(act.actor)}</span> &bull; <span>${escapeHtml(act.timestamp)}</span>
            </div>
          </div>
        `;
        DOM.ovActivityList.appendChild(item);
      });
    }
  }

  // =========================================================================
  // View 2: Inventory
  // =========================================================================
  async function loadInventory() {
    const q = new URLSearchParams();
    if (state.inventoryFilters.search) q.set('search', state.inventoryFilters.search);
    if (state.inventoryFilters.risk !== 'ALL') q.set('risk', state.inventoryFilters.risk);
    if (state.inventoryFilters.manifest !== 'ALL') q.set('manifest', state.inventoryFilters.manifest);

    const data = await apiFetch(`/api/dependencies?${q.toString()}`);
    if (!data) return;
    state.inventoryData = data;

    const countElem = document.getElementById('inv-filtered-count');
    if (countElem) {
      countElem.textContent = `${data.filtered_count} of ${data.total_count} Dependencies`;
    }

    DOM.invTbody.innerHTML = '';
    if (data.dependencies.length === 0) {
      DOM.invTbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 32px; color: var(--text-muted);">
            No dependencies matched your filter criteria.
          </td>
        </tr>
      `;
      return;
    }

    data.dependencies.forEach(dep => {
      const tr = document.createElement('tr');
      tr.style.cursor = 'pointer';

      // AST Usage summary
      let astHtml = '<span style="color: var(--text-muted);">&mdash;</span>';
      if (dep.ast_usage.is_used) {
        astHtml = `<span class="badge badge-green">${dep.ast_call_count} calls in ${dep.ast_files_used.length} file(s)</span>`;
      } else {
        astHtml = `<span class="badge badge-neutral">0 calls (Ghost / Tooling)</span>`;
      }

      // Verification Status badge
      let verBadge = `<span class="badge badge-neutral">${escapeHtml(dep.verification_status)}</span>`;
      if (dep.verification_status === 'BASELINE_FAILURE') {
        verBadge = `<span class="badge badge-red">BASELINE FAIL</span>`;
      } else if (dep.verification_status === 'PENDING_SANDBOX') {
        verBadge = `<span class="badge badge-amber">PENDING SANDBOX</span>`;
      } else if (dep.verification_status === 'NO_ACTION_NEEDED') {
        verBadge = `<span class="badge badge-green">SAFE</span>`;
      }

      tr.innerHTML = `
        <td class="pkg-cell">
          <span class="pkg-name">${escapeHtml(dep.name)}</span>
          ${dep.is_dev ? '<span class="badge badge-neutral" style="font-size: 10px;">DEV</span>' : ''}
          ${dep.has_manifest_conflict ? '<span class="badge badge-red" style="font-size: 10px;">CONFLICT</span>' : ''}
        </td>
        <td>
          <span class="${getSeverityBadge(dep.severity)}">${escapeHtml(dep.severity)}</span>
        </td>
        <td style="font-family: var(--font-mono); font-size: 12px;">
          ${escapeHtml(dep.pinned_version !== 'None' ? dep.pinned_version : (dep.specifiers.join(', ') || 'Any'))}
        </td>
        <td style="font-size: 12px;">
          ${escapeHtml(dep.manifest_files.join(', '))}
        </td>
        <td>${astHtml}</td>
        <td>${verBadge}</td>
        <td>
          <button class="btn-secondary btn-inspect" data-pkg="${escapeHtml(dep.name)}">
            Inspect &rarr;
          </button>
        </td>
      `;

      // Row click opens drawer
      tr.addEventListener('click', (e) => {
        if (!e.target.closest('button')) {
          openDrawer(dep);
        }
      });

      // Button click opens drawer
      tr.querySelector('.btn-inspect').addEventListener('click', () => {
        openDrawer(dep);
      });

      DOM.invTbody.appendChild(tr);
    });
  }

  // Slide-Over Drawer for Dependency Details
  function openDrawer(dep) {
    DOM.drawerPkgName.textContent = dep.name;
    DOM.drawerPkgBadge.className = getSeverityBadge(dep.severity);
    DOM.drawerPkgBadge.textContent = dep.severity;

    // Declarations list
    const declsHtml = dep.declarations.map(d => `
      <div class="kv-item">
        <span class="kv-key">${escapeHtml(d.source_file)}:${d.line_number}</span>
        <span class="kv-val"><code>${escapeHtml(d.raw_line)}</code></span>
      </div>
    `).join('');

    // AST occurrences
    let astHtml = '<div style="color: var(--text-muted); font-size: 12px;">Not referenced in scanned Python source files.</div>';
    if (dep.ast_usage.is_used) {
      const importsList = dep.ast_usage.imports || [];
      const callSitesList = dep.ast_usage.call_sites || [];
      astHtml = `
        <div style="font-size: 12px; font-weight: 600; margin-bottom: 6px; color: var(--semantic-green);">
          ${dep.ast_call_count} occurrences across ${dep.ast_files_used.length} modules
        </div>
        <div class="kv-list">
          ${importsList.map(imp => `
            <div class="kv-item">
              <span class="kv-key">${escapeHtml(imp.file_path)}:${imp.line_number}</span>
              <span class="kv-val"><code>${escapeHtml(imp.statement || 'import')}</code></span>
            </div>
          `).join('')}
          ${callSitesList.map(cs => `
            <div class="kv-item">
              <span class="kv-key">${escapeHtml(cs.file_path)}:${cs.line_number}</span>
              <span class="kv-val"><code>${escapeHtml(cs.code_snippet || cs.call_expression || '')}</code></span>
            </div>
          `).join('')}
        </div>
      `;
    }

    DOM.drawerContent.innerHTML = `
      <div style="margin-bottom: 16px;">
        <div class="section-label">Objective Evidence & Vulnerabilities</div>
        ${dep.objective_risks.length > 0 ? dep.objective_risks.map(r => `
          <div style="font-size: 12px; background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); padding: 8px 10px; border-radius: var(--radius-sm); margin-bottom: 6px;">
            ${escapeHtml(r)}
          </div>
        `).join('') : '<div style="color: var(--semantic-green); font-size: 12px;">No objective risk indicators detected.</div>'}
      </div>

      <div style="margin-bottom: 16px;">
        <div class="section-label">Manifest Declarations</div>
        <div class="kv-list">${declsHtml}</div>
      </div>

      <div style="margin-bottom: 16px;">
        <div class="section-label">Static AST Usage</div>
        <div>${astHtml}</div>
      </div>

      <div>
        <div class="section-label">PyPI Registry Telemetry</div>
        <div class="kv-list">
          <div class="kv-item">
            <span class="kv-key">Latest Release</span>
            <span class="kv-val"><code>${escapeHtml(dep.pypi_metadata.latest_version || 'Unknown')}</code> (${escapeHtml(dep.pypi_metadata.latest_release_date || 'Unknown')})</span>
          </div>
          <div class="kv-item">
            <span class="kv-key">Requires Python</span>
            <span class="kv-val"><code>${escapeHtml(dep.pypi_metadata.requires_python || 'Any')}</code></span>
          </div>
          <div class="kv-item">
            <span class="kv-key">Homepage</span>
            <span class="kv-val">${dep.pypi_metadata.home_page ? `<a href="${escapeHtml(dep.pypi_metadata.home_page)}" target="_blank" style="color: var(--semantic-violet);">${escapeHtml(dep.pypi_metadata.home_page)}</a>` : 'None'}</span>
          </div>
        </div>
      </div>

      <div style="margin-top: 10px; padding-top: 14px; border-top: 1px solid var(--border-subtle);">
        <button class="btn-primary" style="width: 100%; justify-content: center;" id="drawer-wb-btn">
          Open in Migration Workbench &rarr;
        </button>
      </div>
    `;

    DOM.drawerBackdrop.classList.add('open');
    DOM.drawerPanel.classList.add('open');

    document.getElementById('drawer-wb-btn')?.addEventListener('click', () => {
      closeDrawer();
      window.location.hash = `#workbench?pkg=${encodeURIComponent(dep.name)}`;
    });
  }

  function closeDrawer() {
    DOM.drawerBackdrop.classList.remove('open');
    DOM.drawerPanel.classList.remove('open');
  }

  DOM.drawerCloseBtn?.addEventListener('click', closeDrawer);
  DOM.drawerBackdrop?.addEventListener('click', closeDrawer);

  // =========================================================================
  // View 3: Migration Workbench
  // =========================================================================
  async function loadWorkbench(selectedPkg = null) {
    const pkgQuery = selectedPkg ? `&package=${encodeURIComponent(selectedPkg)}` : '';
    const data = await apiFetch(`/api/workbench${pkgQuery.replace('&', '?')}`);
    if (!data) return;
    state.workbenchData = data;

    const activePkg = (data.selected_proposal && data.selected_proposal.package_name) || selectedPkg || (data.available_packages && data.available_packages[0]);
    state.selectedWorkbenchPkg = activePkg;

    // Render Package Pills
    DOM.wbPkgBar.innerHTML = '';
    data.all_proposals.forEach(p => {
      const isActive = activePkg && p.package_name.toLowerCase() === activePkg.toLowerCase();
      const btn = document.createElement('button');
      btn.className = `pkg-pill-btn ${isActive ? 'active' : ''}`;
      btn.innerHTML = `
        <span>${escapeHtml(p.package_name)}</span>
        <span class="badge badge-violet" style="font-size: 10px;">${escapeHtml(p.target_action)}</span>
      `;
      btn.addEventListener('click', () => {
        state.selectedWorkbenchPkg = p.package_name;
        loadWorkbench(p.package_name);
      });
      DOM.wbPkgBar.appendChild(btn);
    });

    const proposal = data.selected_proposal;
    if (!proposal) return;

    // Header info
    DOM.wbPkgTitle.textContent = proposal.package_name;
    DOM.wbReplacementTitle.textContent = proposal.recommended_package && proposal.recommended_package !== 'None'
      ? `\u2192 ${proposal.recommended_package}`
      : `(${proposal.target_action})`;

    DOM.wbActionBadge.textContent = proposal.target_action;
    DOM.wbFeasibilityBadge.textContent = proposal.feasibility;

    // Evidence Side (Green Panel)
    const obs = proposal.observed_evidence || {};

    // Declarations
    DOM.wbEvidenceDecls.innerHTML = (obs.declarations || []).map(d => `
      <div class="kv-item">
        <span class="kv-key">${escapeHtml(d.source_file)}:${d.line_number}</span>
        <span class="kv-val"><code>${escapeHtml(d.raw_line)}</code></span>
      </div>
    `).join('') || '<div style="color: var(--text-muted); font-size: 12px;">No manifest records</div>';

    // AST
    const ast = obs.ast_usage || {};
    if (!ast.is_used) {
      DOM.wbEvidenceAst.innerHTML = `
        <div style="font-size: 12px; color: var(--semantic-amber);">
          <strong>Unused Ghost Dependency:</strong> 0 AST occurrences found in scanned files.
        </div>
      `;
    } else {
      const importsList = ast.imports || [];
      const callSitesList = ast.call_sites || [];
      DOM.wbEvidenceAst.innerHTML = importsList.map(imp => `
        <div class="kv-item">
          <span class="kv-key">${escapeHtml(imp.file_path)}:${imp.line_number}</span>
          <span class="kv-val"><code>${escapeHtml(imp.statement || 'import')}</code></span>
        </div>
      `).join('') + callSitesList.map(cs => `
        <div class="kv-item">
          <span class="kv-key">${escapeHtml(cs.file_path)}:${cs.line_number}</span>
          <span class="kv-val"><code>${escapeHtml(cs.code_snippet || cs.call_expression || '')}</code></span>
        </div>
      `).join('');
    }

    // PyPI Facts
    DOM.wbEvidencePypi.innerHTML = `
      <div class="kv-item">
        <span class="kv-key">Latest Version</span>
        <span class="kv-val"><code>${escapeHtml(obs.pypi_metadata.latest_version)}</code> (${escapeHtml(obs.pypi_metadata.release_date)})</span>
      </div>
      ${(obs.objective_risks || []).map(r => `
        <div style="font-size: 11px; color: var(--text-secondary); background: var(--bg-ground); padding: 6px 8px; border-radius: var(--radius-sm); margin-top: 4px;">
          ${escapeHtml(r)}
        </div>
      `).join('')}
    `;

    // Baseline impact
    if (obs.baseline_failure) {
      DOM.wbEvidenceBaseline.innerHTML = `
        <div style="background: var(--semantic-red-bg); border: 1px solid var(--semantic-red-border); color: var(--semantic-red); padding: 8px 10px; border-radius: var(--radius-sm);">
          <strong>Critical Pre-Existing Baseline Crash:</strong> ${escapeHtml(obs.baseline_failure_details)}
        </div>
      `;
    } else {
      DOM.wbEvidenceBaseline.innerHTML = `
        <span style="color: var(--semantic-green);">Passed in upstream baseline test suite without individual import crashes.</span>
      `;
    }

    // Gemma Recommendation (Violet Panel)
    DOM.wbRationaleText.textContent = proposal.rationale || 'Architectural rationale synthesized based on AST and PyPI facts.';
    DOM.wbStepsList.innerHTML = (proposal.migration_steps || []).map(step => `
      <li style="margin-bottom: 4px;">${escapeHtml(step)}</li>
    `).join('');

    DOM.wbGapsText.textContent = proposal.compatibility_gaps_and_limitations || 'None reported. Verification required.';

    // Code Diff
    renderDiff(proposal.unified_diff || 'No unified diff file recorded for this proposal.');

    // Wire copy button
    DOM.wbCopyDiffBtn.onclick = () => {
      if (proposal.unified_diff) {
        navigator.clipboard.writeText(proposal.unified_diff).then(() => {
          showToast('Unified diff copied to clipboard', 'success');
        }).catch(() => {
          showToast('Failed to copy to clipboard', 'error');
        });
      }
    };
  }

  function renderDiff(diffText) {
    DOM.wbDiffContent.innerHTML = '';
    const lines = diffText.split('\n');

    lines.forEach(line => {
      const span = document.createElement('span');
      span.className = 'diff-line';

      if (line.startsWith('+') && !line.startsWith('+++')) {
        span.className += ' diff-add';
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        span.className += ' diff-del';
      } else if (line.startsWith('@@')) {
        span.className += ' diff-hunk';
      }

      span.textContent = line;
      DOM.wbDiffContent.appendChild(span);
    });
  }

  // =========================================================================
  // View 4: Verification Runs
  // =========================================================================
  async function loadRuns() {
    const data = await apiFetch('/api/runs');
    if (!data) return;
    state.runsData = data;

    // Update Live Action Banner
    if (DOM.runsProjectNameDisplay) {
      DOM.runsProjectNameDisplay.textContent = state.currentProject === 'swasthyavaani'
        ? 'SwasthyaVaani (Clinical EHR Platform)'
        : 'LinkWatch (Track 1 Target)';
    }
    if (DOM.runsCommandDisplay) {
      DOM.runsCommandDisplay.textContent = state.currentProject === 'swasthyavaani'
        ? 'pytest tests/test_safety_rules.py -v'
        : 'pytest -q --disable-warnings -v LinkWatch/tests';
    }

    if (!DOM.runsCardsContainer) return;
    DOM.runsCardsContainer.innerHTML = '';

    (data.runs || []).forEach((run) => {
      const card = document.createElement('div');
      card.className = 'run-card';
      if (run.run_type === 'POST_MIGRATION_CANDIDATE' && run.verdict !== 'VERIFIED_SUCCESS') {
        card.style.borderColor = 'var(--semantic-amber-border)';
      }

      const isFail = run.execution.exit_code !== 0 || run.execution.verdict === 'FAILED';
      const isVerified = run.execution.verdict === 'VERIFIED_SUCCESS' || run.execution.exit_code === 0;

      let badgeHtml = '';
      if (isFail) {
        badgeHtml = `<span class="badge badge-red">Exit Code ${run.execution.exit_code}</span>`;
      } else if (isVerified) {
        badgeHtml = `<span class="badge badge-green">Exit Code 0 (Passed)</span>`;
      } else {
        badgeHtml = `<span class="badge badge-amber">${escapeHtml(run.execution.verdict)}</span>`;
      }

      let kvHtml = '';
      if (run.environment) {
        kvHtml += `
          <div class="kv-item">
            <span class="kv-key">Target Environment</span>
            <span class="kv-val">${escapeHtml(run.environment.target || run.environment.python_executable || 'Python')}</span>
          </div>
        `;
      }
      if (run.execution) {
        kvHtml += `
          <div class="kv-item">
            <span class="kv-key">Test Outcomes</span>
            <span class="kv-val">
              <span class="badge badge-green">${run.execution.passed_count || 0} Passed</span>
              ${run.execution.failed_count ? `<span class="badge badge-red">${run.execution.failed_count} Failed</span>` : ''}
              <span class="badge badge-neutral">${run.execution.total_collected || 0} Collected</span>
              <span style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">(${run.execution.duration_seconds || 0}s)</span>
            </span>
          </div>
        `;
      }

      if (run.failures && run.failures.length > 0) {
        kvHtml += `
          <div class="kv-item">
            <span class="kv-key">Pre-Existing Failure</span>
            <span class="kv-val" style="color: var(--semantic-red);">
              <code>${escapeHtml(run.failures[0].test_id || '')}</code>
            </span>
          </div>
          <div class="kv-item">
            <span class="kv-key">Failure Diagnostic</span>
            <span class="kv-val" style="color: var(--semantic-red);">
              <code>${escapeHtml(run.failures[0].failure_type || '')}: ${escapeHtml(run.failures[0].message || '')}</code>
            </span>
          </div>
        `;
      }

      let logBoxHtml = '';
      if (run.log_excerpt) {
        logBoxHtml = `
          <div class="diff-toolbar" style="border-radius: var(--radius-sm) var(--radius-sm) 0 0; margin-top: 14px;">
            <span class="diff-filename">${escapeHtml(run.log_file || 'Execution Output Log')}</span>
          </div>
          <div class="terminal-box" style="max-height: 260px; overflow-y: auto;">${escapeHtml(run.log_excerpt)}</div>
        `;
      } else if (run.status_explanation) {
        logBoxHtml = `
          <p style="font-size: 13px; color: var(--text-primary); margin-top: 12px; line-height: 1.6;">
            ${escapeHtml(run.status_explanation)}
          </p>
        `;
      }

      card.innerHTML = `
        <div class="run-header">
          <div class="run-title-area">
            ${badgeHtml}
            <span class="run-title">${escapeHtml(run.label)}</span>
          </div>
          <div style="font-size: 12px; font-family: var(--font-mono); color: var(--text-secondary);">
            <code>${escapeHtml(run.execution.test_command || '')}</code>
          </div>
        </div>
        <div style="padding: 16px 18px;">
          <div class="kv-list">${kvHtml}</div>
          ${logBoxHtml}
        </div>
      `;
      DOM.runsCardsContainer.appendChild(card);
    });
  }

  // =========================================================================
  // View 5: Exit Capsules
  // =========================================================================
  async function loadCapsules() {
    const data = await apiFetch('/api/capsules');
    if (!data) return;
    state.capsulesData = data;
  }

  // =========================================================================
  // View 6: Settings
  // =========================================================================
  async function loadSettings() {
    const data = await apiFetch('/api/settings');
    if (!data) return;
    state.settingsData = data;

    if (DOM.settingsTargetPath) {
      DOM.settingsTargetPath.textContent = data.target_repository.local_path;
    }
    if (DOM.settingsUpstreamCommit) {
      DOM.settingsUpstreamCommit.textContent = data.target_repository.commit_sha;
    }
    if (DOM.settingsPypiCache) {
      DOM.settingsPypiCache.textContent = `${data.cache_and_runtime.pypi_cache_file} (${data.cache_and_runtime.cached_packages_count} entries cached)`;
    }
  }

  // =========================================================================
  // Live Test Suite Execution Action
  // =========================================================================
  async function executeProjectTests() {
    const isRunning = (DOM.btnRunTests && DOM.btnRunTests.disabled) || (DOM.btnRunsExecuteNow && DOM.btnRunsExecuteNow.disabled);
    if (isRunning) return;

    if (DOM.btnRunTests) {
      DOM.btnRunTests.disabled = true;
      if (DOM.runTestsBtnText) DOM.runTestsBtnText.textContent = 'Running...';
    }
    if (DOM.btnRunsExecuteNow) {
      DOM.btnRunsExecuteNow.disabled = true;
      if (DOM.runsExecuteBtnText) DOM.runsExecuteBtnText.textContent = 'Running Pytest...';
    }

    const projLabel = state.currentProject === 'swasthyavaani' ? 'SwasthyaVaani' : 'LinkWatch';
    showToast(`Executing pytest test suite on ${projLabel}...`, 'info');

    try {
      const res = await fetch('/api/run-tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: state.currentProject })
      });
      const data = await res.json();

      const isPassed = data.exit_code === 0;
      const msg = `Tests ${data.verdict} on ${data.display_name}: ${data.passed_count} passed, ${data.failed_count} failed in ${data.duration_seconds}s`;
      showToast(msg, isPassed ? 'success' : 'error');

      // Clear cached data so the live run output is immediately reflected
      state.runsData = null;
      state.overviewData = null;

      if (state.currentView === 'runs') {
        loadRuns();
      } else if (state.currentView === 'overview') {
        loadOverview();
      }
    } catch (err) {
      showToast('Error executing tests: ' + err.message, 'error');
    } finally {
      if (DOM.btnRunTests) {
        DOM.btnRunTests.disabled = false;
        if (DOM.runTestsBtnText) DOM.runTestsBtnText.textContent = 'Run Tests';
      }
      if (DOM.btnRunsExecuteNow) {
        DOM.btnRunsExecuteNow.disabled = false;
        if (DOM.runsExecuteBtnText) DOM.runsExecuteBtnText.textContent = 'Execute Test Suite Now';
      }
    }
  }

  // =========================================================================
  // User Actions & Event Listeners
  // =========================================================================

  // Project Selector Change
  DOM.projectSelect?.addEventListener('change', (e) => {
    handleProjectChange(e.target.value);
  });

  // Run Tests Buttons
  DOM.btnRunTests?.addEventListener('click', executeProjectTests);
  DOM.btnRunsExecuteNow?.addEventListener('click', executeProjectTests);

  // Analyze Repository Button Action
  DOM.btnAnalyze?.addEventListener('click', async () => {
    DOM.btnAnalyze.disabled = true;
    DOM.analyzeBtnText.textContent = 'Analyzing...';
    DOM.btnAnalyze.style.opacity = '0.7';

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project: state.currentProject })
      });
      const result = await res.json();
      showToast(result.message || 'Repository scan refreshed successfully.', 'success');

      state.overviewData = null;
      state.inventoryData = null;
      if (state.currentView === 'overview') loadOverview();
      if (state.currentView === 'inventory') loadInventory();
    } catch (err) {
      showToast('Analysis error: ' + err.message, 'error');
    } finally {
      DOM.btnAnalyze.disabled = false;
      DOM.analyzeBtnText.textContent = 'Analyze Repository';
      DOM.btnAnalyze.style.opacity = '1';
    }
  });

  // Inventory Filters
  let searchDebounceTimer = null;
  DOM.invSearchInput?.addEventListener('input', (e) => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      state.inventoryFilters.search = e.target.value.trim();
      loadInventory();
    }, 200);
  });

  DOM.invRiskSelect?.addEventListener('change', (e) => {
    state.inventoryFilters.risk = e.target.value;
    loadInventory();
  });

  DOM.invManifestSelect?.addEventListener('change', (e) => {
    state.inventoryFilters.manifest = e.target.value;
    loadInventory();
  });

  DOM.invResetBtn?.addEventListener('click', () => {
    state.inventoryFilters.search = '';
    state.inventoryFilters.risk = 'ALL';
    state.inventoryFilters.manifest = 'ALL';
    if (DOM.invSearchInput) DOM.invSearchInput.value = '';
    if (DOM.invRiskSelect) DOM.invRiskSelect.value = 'ALL';
    if (DOM.invManifestSelect) DOM.invManifestSelect.value = 'ALL';
    loadInventory();
  });

  // Mobile Menu Toggle
  DOM.mobileToggleBtn?.addEventListener('click', () => {
    DOM.sidebar?.classList.toggle('mobile-open');
  });

  // Hash Change Event
  window.addEventListener('hashchange', () => {
    navigateTo(window.location.hash);
  });

  // Keyboard navigation escape drawer
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeDrawer();
    }
  });

  // Theme Switching: Warm Light (Default) vs Dark Slate
  function applyTheme(themeName) {
    if (themeName === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
      if (DOM.themeBtnLabel) DOM.themeBtnLabel.textContent = 'Dark Slate';
      localStorage.setItem('resilify-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
      if (DOM.themeBtnLabel) DOM.themeBtnLabel.textContent = 'Warm Light';
      localStorage.setItem('resilify-theme', 'warm-light');
    }
  }

  function toggleTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
      applyTheme('warm-light');
      showToast('Palette: Warm Light (#F7F6F2)', 'info');
    } else {
      applyTheme('dark');
      showToast('Palette: Dark Slate (#0A0E17)', 'info');
    }
  }

  DOM.btnThemeToggle?.addEventListener('click', toggleTheme);

  // Initialize Application
  async function init() {
    const savedTheme = localStorage.getItem('resilify-theme') || 'warm-light';
    applyTheme(savedTheme);
    await loadProjects();
    navigateTo(window.location.hash);
  }

  // DOM ready check
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
