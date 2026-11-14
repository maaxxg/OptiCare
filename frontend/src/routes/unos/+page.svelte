<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import { addPatient } from '#lib/stores/patients.js';
	import { setPendingNotification } from '#lib/stores/notification.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	let name = $state('');
	let location = $state('');
	let needsTransport = $state(false);
	let willingToDrive = $state(false);
	let description = $state('');
	let error = $state('');

	// Side panel stanje
	let sidePanelOpen = $state(false);
	let examTime = $state('');
	let departureTime = $state('');
	let returnTime = $state('');

	const locations = [
		'Gospić',
		'Otočac',
		'Senj',
		'Korenica',
		'Novalja',
		'Perušić',
		'Brinje',
		'Donji Lapac',
		'Vrhovine',
		'Udbina',
		'Plitvička Jezera',
		'Lovinac',
		'Karlobag'
	];

	function openSidePanel() {
		sidePanelOpen = true;
	}

	function closeSidePanel() {
		sidePanelOpen = false;
	}

	function handleSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';

		if (!name.trim()) {
			error = 'Unesite ime i prezime pacijenta.';
			return;
		}
		if (!location) {
			error = 'Odaberite mjesto stanovanja.';
			return;
		}
		if (!description.trim()) {
			error = 'Unesite opis problema pacijenta.';
			return;
		}

		const newPatient = addPatient({
			name: name.trim(),
			location,
			needsTransport,
			willingToDrive,
			description: description.trim(),
			examTime: examTime || undefined,
			departureTime: departureTime || undefined,
			returnTime: returnTime || undefined
		});

		// Postavi notifikaciju za raspored stranicu
		setPendingNotification({
			patientName: newPatient.name,
			description: newPatient.description,
			location: newPatient.location,
			examTime: newPatient.examTime,
			departureTime: newPatient.departureTime,
			returnTime: newPatient.returnTime,
			needsTransport: newPatient.needsTransport,
			onHold: false
		});

		// Preusmjeri na raspored
		goto(resolve('/raspored'));
	}

	function goBack() {
		goto(resolve('/'));
	}
</script>

<svelte:head>
	<title>OptiCare — Unos pacijenta</title>
</svelte:head>

<!-- Side panel trigger gumb -->
<button class="side-panel-trigger" onclick={openSidePanel} aria-label="Unos vremena pregleda">
	⏰ Vrijeme
</button>

<!-- Side panel overlay -->
{#if sidePanelOpen}
	<div
		class="side-panel-overlay"
		onclick={closeSidePanel}
		onkeydown={(e) => {
			if (e.key === 'Escape') closeSidePanel();
		}}
		role="button"
		tabindex="0"
		aria-label="Zatvori panel"
	></div>
{/if}

<!-- Side panel -->
<div class="side-panel" class:open={sidePanelOpen}>
	<div class="side-panel-header">
		<h3 class="side-panel-title">Ručni unos vremena</h3>
		<button class="side-panel-close" onclick={closeSidePanel} aria-label="Zatvori">✕</button>
	</div>
	<p class="side-panel-desc">Opcionalno — unesite vremena ručno ako ih znate unaprijed.</p>

	<div class="form-group">
		<label class="form-label" for="exam-time">Vrijeme pregleda</label>
		<input id="exam-time" class="form-input" type="time" bind:value={examTime} />
	</div>

	<div class="form-group">
		<label class="form-label" for="departure-time">Vrijeme polaska</label>
		<input id="departure-time" class="form-input" type="time" bind:value={departureTime} />
	</div>

	<div class="form-group">
		<label class="form-label" for="return-time">Vrijeme povratka</label>
		<input id="return-time" class="form-input" type="time" bind:value={returnTime} />
	</div>

	<button class="btn-primary" onclick={closeSidePanel} style="margin-top: 8px;">
		Spremi vremena
	</button>

	{#if examTime || departureTime || returnTime}
		<div class="time-summary">
			{#if departureTime}<div>🚌 Polazak: <strong>{departureTime}</strong></div>{/if}
			{#if examTime}<div>🏥 Pregled: <strong>{examTime}</strong></div>{/if}
			{#if returnTime}<div>🏠 Povratak: <strong>{returnTime}</strong></div>{/if}
		</div>
	{/if}
</div>

<div class="page">
	<div class="page-header">
		<img src={logo} alt="OptiCare" class="logo-full" />
		<button class="back-link" onclick={goBack}>← Povratak</button>
	</div>

	<h1 class="page-title">Ispunite podatke o pacijentu</h1>

	<!-- Indikator unesenih vremena -->
	{#if examTime || departureTime || returnTime}
		<div class="time-indicator">
			⏰ Vremena unesena:
			{#if departureTime}<span>Polazak {departureTime}</span>{/if}
			{#if examTime}<span>Pregled {examTime}</span>{/if}
			{#if returnTime}<span>Povratak {returnTime}</span>{/if}
		</div>
	{/if}

	<form onsubmit={handleSubmit} class="intake-form">
		<div class="two-col">
			<div>
				<div class="form-group">
					<label class="form-label" for="patient-name">Ime i prezime</label>
					<input id="patient-name" class="form-input" type="text" bind:value={name} />
				</div>

				<div class="form-group">
					<label class="form-label" for="location">Mjesto stanovanja</label>
					<select id="location" class="form-select" bind:value={location}>
						<option value="" disabled selected hidden></option>
						{#each locations as loc (loc)}
							<option value={loc}>{loc}</option>
						{/each}
					</select>
				</div>
			</div>

			<div class="radio-box">
				<div class="radio-box-header-row">
					<span class="radio-box-spacer"></span>
					<div class="radio-cols-header">
						<span class="col-head">Da</span>
						<span class="col-head">Ne</span>
					</div>
				</div>

				<div class="radio-box-row">
					<span class="radio-box-label">Treba prijevoz</span>
					<div class="radio-cols-options">
						<label class="radio-cell">
							<input
								type="radio"
								name="transport"
								value="true"
								checked={needsTransport === true}
								onchange={() => (needsTransport = true)}
							/>
						</label>
						<label class="radio-cell">
							<input
								type="radio"
								name="transport"
								value="false"
								checked={needsTransport === false}
								onchange={() => (needsTransport = false)}
							/>
						</label>
					</div>
				</div>

				<div class="radio-box-row">
					<span class="radio-box-label">Nudi prijevoz drugima</span>
					<div class="radio-cols-options">
						<label class="radio-cell">
							<input
								type="radio"
								name="willing"
								value="true"
								checked={willingToDrive === true}
								onchange={() => (willingToDrive = true)}
							/>
						</label>
						<label class="radio-cell">
							<input
								type="radio"
								name="willing"
								value="false"
								checked={willingToDrive === false}
								onchange={() => (willingToDrive = false)}
							/>
						</label>
					</div>
				</div>
			</div>
		</div>

		<div class="form-group" style="margin-top: 20px;">
			<label class="form-label" for="description">Opis problema pacijenta</label>
			<textarea id="description" class="form-textarea" bind:value={description}></textarea>
		</div>

		{#if error}
			<p class="error-text">{error}</p>
		{/if}

		<button type="submit" class="btn-primary">Spremi i prikaži raspored</button>
	</form>
</div>

<style>
	.intake-form {
		margin-top: 24px;
	}

	/* ─── Side panel ────────────────────── */
	.side-panel-trigger {
		position: fixed;
		right: 0;
		top: 50%;
		transform: translateY(-50%);
		background: var(--green);
		color: white;
		border: none;
		padding: 16px 8px;
		border-radius: 12px 0 0 12px;
		cursor: pointer;
		writing-mode: vertical-lr;
		font-weight: 600;
		font-size: 0.9rem;
		z-index: 50;
		box-shadow: var(--shadow-md);
		font-family: var(--font-sans);
		transition: background 0.2s;
		letter-spacing: 0.03em;
	}

	.side-panel-trigger:hover {
		background: var(--green-dark);
	}

	.side-panel-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 199;
	}

	.side-panel {
		position: fixed;
		top: 0;
		right: 0;
		width: 320px;
		max-width: 90vw;
		height: 100vh;
		background: #fff;
		box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
		padding: 32px 24px;
		z-index: 200;
		transform: translateX(100%);
		transition: transform 0.3s ease;
		overflow-y: auto;
	}

	.side-panel.open {
		transform: translateX(0);
	}

	.side-panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 12px;
	}

	.side-panel-title {
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--text);
	}

	.side-panel-close {
		background: none;
		border: none;
		font-size: 1.1rem;
		cursor: pointer;
		color: var(--text-muted);
		padding: 4px 8px;
		border-radius: 8px;
		transition: background 0.2s;
	}

	.side-panel-close:hover {
		background: var(--green-light);
	}

	.side-panel-desc {
		font-size: 0.85rem;
		color: var(--text-muted);
		margin-bottom: 24px;
		line-height: 1.5;
	}

	.time-summary {
		margin-top: 20px;
		padding: 14px 16px;
		background: var(--green-light);
		border-radius: var(--radius-md);
		font-size: 0.9rem;
		display: flex;
		flex-direction: column;
		gap: 6px;
		color: var(--text);
	}

	/* ─── Time indicator on main page ── */
	.time-indicator {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
		background: var(--green-light);
		border: 1.5px solid var(--border);
		border-radius: var(--radius-md);
		padding: 10px 18px;
		font-size: 0.88rem;
		font-weight: 500;
		color: var(--text);
		margin-bottom: 16px;
	}

	.time-indicator span {
		background: white;
		border: 1px solid var(--border);
		border-radius: var(--radius-pill);
		padding: 3px 12px;
		font-weight: 600;
	}
</style>
