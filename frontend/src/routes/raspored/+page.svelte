<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import { getPatients, generateSimulatedTimes, type Patient } from '#lib/stores/patients.js';
	import {
		getPendingNotification,
		clearPendingNotification,
		updatePendingNotification,
		type PendingNotification
	} from '#lib/stores/notification.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	const patients: Patient[] = getPatients();

	const groups = [
		{
			color: 'peach',
			title: 'Treba prijevoz – čeka planiranje',
			rows: patients.filter((p) => p.needsTransport)
		},
		{
			color: 'green',
			title: 'Dolazi samostalno',
			rows: patients.filter((p) => !p.needsTransport)
		}
	];

	// Modal / notifikacija
	let notification: PendingNotification | null = $state(null);
	let showModal = $state(false);

	onMount(() => {
		const pending = getPendingNotification();
		if (pending) {
			notification = pending;
			if (!pending.onHold) {
				showModal = true;
			}
		}
	});

	function acceptTerm() {
		clearPendingNotification();
		notification = null;
		showModal = false;
	}

	function recommendNewTerm() {
		if (notification) {
			const newTimes = generateSimulatedTimes();
			notification.examTime = newTimes.examTime;
			notification.departureTime = newTimes.departureTime;
			notification.returnTime = newTimes.returnTime;
			updatePendingNotification(notification);
		}
	}

	function manualEntry() {
		clearPendingNotification();
		notification = null;
		showModal = false;
		goto(resolve('/unos'));
	}

	function cancelAction() {
		clearPendingNotification();
		notification = null;
		showModal = false;
	}

	function putOnHold() {
		if (notification) {
			notification.onHold = true;
			updatePendingNotification(notification);
		}
		showModal = false;
	}

	function resumeFromHold() {
		if (notification) {
			notification.onHold = false;
			showModal = true;
		}
	}
</script>

<svelte:head>
	<title>OptiCare — Raspored pacijenata</title>
</svelte:head>

<div class="page-wide">
	<div class="schedule-top-nav">
		<img src={logo} alt="OptiCare" class="logo-full" />
		<button class="back-link" onclick={() => goto(resolve('/'))}>← Povratak</button>
	</div>

	<!-- On-hold banner -->
	{#if notification && notification.onHold}
		<div class="on-hold-banner">
			<span>⏸ Termin za <strong>{notification.patientName}</strong> je na čekanju</span>
			<button class="btn-resume" onclick={resumeFromHold}>Nastavi</button>
		</div>
	{/if}

	<div class="schedule-header-row">
		<h1 class="schedule-main-title">Raspored pacijenata</h1>
	</div>

	<div class="schedule-legend">
		{#each groups as group (group.color)}
			<div class="legend-item">
				<div class="legend-square {group.color}"></div>
				<span>{group.title}</span>
			</div>
		{/each}
	</div>

	{#if patients.length === 0}
		<p class="empty-state">Još nema unesenih zahtjeva.</p>
	{:else}
		<div class="schedule-table-wrap">
			<div class="schedule-table">
				<div class="table-header-pill">
					<span>Osoba</span>
					<span>Opis problema</span>
					<span>Mjesto stanovanja</span>
					<span class="center-col">Vrijeme polaska</span>
					<span class="center-col">Vrijeme pregleda</span>
					<span class="center-col">Vrijeme povratka</span>
				</div>

				{#each groups as group (group.color)}
					{#if group.rows.length > 0}
						<section class="schedule-group">
							<div class="group-title {group.color}">{group.title}</div>
							<div class="group-container {group.color}">
								{#each group.rows as p (p.id)}
									<div class="schedule-row">
										<div class="col-person">
											{p.name}
											{#if p.willingToDrive}
												<br /><span class="badge badge-green">Nudi prijevoz</span>
											{/if}
										</div>
										<div class="col-exam">{p.description}</div>
										<div class="col-clinic">{p.location}</div>
										<span class="center-col">
											<span class="time-badge-pill">{p.departureTime ?? '—'}</span>
										</span>
										<span class="center-col">
											<span class="time-badge-pill">{p.examTime ?? '—'}</span>
										</span>
										<span class="center-col">
											<span class="time-badge-pill">{p.returnTime ?? '—'}</span>
										</span>
									</div>
								{/each}
							</div>
						</section>
					{/if}
				{/each}
			</div>
		</div>
	{/if}
</div>

<!-- Modal popup notifikacija -->
{#if showModal && notification}
	<div
		class="modal-overlay"
		onclick={cancelAction}
		onkeydown={(e) => {
			if (e.key === 'Escape') cancelAction();
		}}
		role="button"
		tabindex="0"
		aria-label="Zatvori notifikaciju"
	>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<div class="modal-card" onclick={(e) => e.stopPropagation()} role="document">
			<h2 class="modal-title" id="modal-title">Odgovor agenta umjetne inteligencije:</h2>
			<p class="modal-text">
				Nakon analize podataka pacijenta preporučam termin za
				<strong>{notification.description}</strong> u
				<strong>{notification.location}</strong>{#if notification.examTime}
					u <strong>{notification.examTime}</strong>{/if}{#if notification.needsTransport},
					organizirani prijevoz bi pokupio pacijenta{#if notification.departureTime}
						u <strong>{notification.departureTime}</strong>{/if}{#if notification.returnTime}
						i pretpostavljeno vrijeme povratka je
						<strong>{notification.returnTime}</strong>{/if}{/if}.
			</p>

			<div class="modal-actions">
				<button class="modal-btn modal-btn-green" onclick={acceptTerm}> Prihvati termin </button>
				<button class="modal-btn modal-btn-outline" onclick={recommendNewTerm}>
					Preporuči novi termin
				</button>
				<button class="modal-btn modal-btn-outline" onclick={manualEntry}>
					Ručno upiši novi termin
				</button>
				<button class="modal-btn modal-btn-red" onclick={cancelAction}> Prekid radnji </button>
				<button class="modal-btn modal-btn-yellow" onclick={putOnHold}> ⏸ Stavi na čekanje </button>
			</div>
		</div>
	</div>
{/if}

<style>
	/* ─── Modal ────────────────────────── */
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 300;
	}

	.modal-card {
		background: #fff;
		border-radius: 24px;
		padding: 36px 32px;
		max-width: 400px;
		width: 90vw;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
		text-align: center;
	}

	.modal-title {
		font-size: 1.4rem;
		font-weight: 800;
		margin-bottom: 16px;
		color: var(--text);
	}

	.modal-text {
		font-size: 0.95rem;
		color: var(--text-muted);
		margin-bottom: 28px;
		line-height: 1.6;
	}

	.modal-actions {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.modal-btn {
		width: 100%;
		padding: 14px 20px;
		border-radius: var(--radius-pill);
		font-size: 1rem;
		font-weight: 600;
		font-family: var(--font-sans);
		cursor: pointer;
		transition:
			opacity 0.2s,
			transform 0.1s;
		border: 2px solid transparent;
	}

	.modal-btn:active {
		transform: scale(0.98);
	}

	.modal-btn-green {
		background: var(--green);
		color: white;
		border-color: var(--green-dark);
	}

	.modal-btn-outline {
		background: white;
		color: var(--text);
		border-color: #d4d4d4;
	}

	.modal-btn-red {
		background: #fce4e4;
		color: #c0392b;
		border-color: #f0c0c0;
	}

	.modal-btn-yellow {
		background: #fff3cd;
		color: #856404;
		border-color: #ffc107;
	}

	/* ─── On-hold banner ────────────────── */
	.on-hold-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		background: #fff3cd;
		border: 1px solid #ffc107;
		border-radius: var(--radius-md);
		padding: 12px 20px;
		margin-bottom: 20px;
		font-size: 0.92rem;
	}

	.btn-resume {
		background: var(--green);
		color: white;
		border: none;
		padding: 8px 20px;
		border-radius: var(--radius-pill);
		font-weight: 600;
		cursor: pointer;
		font-size: 0.85rem;
		font-family: var(--font-sans);
	}

	.btn-resume:hover {
		opacity: 0.9;
	}
</style>
