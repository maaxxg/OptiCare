<script lang="ts">
	import logo from '#lib/assets/opticare-logo.svg';
	import { addPatient } from '#lib/stores/patients.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	let name = $state('');
	let location = $state('');
	let needsTransport = $state(false);
	let willingToDrive = $state(false);
	let description = $state('');
	let error = $state('');
	let confirmDialog: HTMLDialogElement | undefined = $state();

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

	function handleWindowKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && sidePanelOpen) closeSidePanel();
	}

	// Only pairs that are present are compared; "HH:MM" strings compare correctly.
	function timesInOrder(): boolean {
		if (departureTime && examTime && departureTime >= examTime) return false;
		if (examTime && returnTime && examTime >= returnTime) return false;
		if (departureTime && returnTime && departureTime >= returnTime) return false;
		return true;
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
		if (!timesInOrder()) {
			error = 'Vremena nisu u ispravnom redoslijedu: polazak, pregled, povratak.';
			return;
		}

		// Nothing is saved yet: the nurse reviews and confirms in the dialog.
		confirmDialog?.showModal();
	}

	function backToEditing() {
		confirmDialog?.close();
	}

	function confirmAndSave() {
		addPatient({
			name: name.trim(),
			location,
			needsTransport,
			willingToDrive,
			description: description.trim(),
			examTime: examTime || undefined,
			departureTime: departureTime || undefined,
			returnTime: returnTime || undefined
		});
		confirmDialog?.close();
		goto(resolve('/raspored'));
	}

	function goBack() {
		goto(resolve('/'));
	}
</script>

<svelte:head>
	<title>OptiCare — Unos pacijenta</title>
</svelte:head>

<svelte:window onkeydown={handleWindowKeydown} />

<!-- Backdrop closes the side panel only; it never saves anything. -->
{#if sidePanelOpen}
	<button
		type="button"
		class="side-panel-overlay"
		onclick={closeSidePanel}
		aria-label="Zatvori panel"
		tabindex="-1"
	></button>
{/if}

<!-- Side panel; inert while closed so it is out of the tab order and hidden from assistive tech -->
<div
	class="side-panel"
	class:open={sidePanelOpen}
	inert={!sidePanelOpen}
	role="dialog"
	aria-label="Ručni unos vremena"
>
	<div class="side-panel-header">
		<h3 class="side-panel-title">Ručni unos vremena</h3>
		<button type="button" class="side-panel-close" onclick={closeSidePanel} aria-label="Zatvori"
			>✕</button
		>
	</div>
	<p class="side-panel-desc">Neobavezno — unesite vremena ručno ako ih znate unaprijed.</p>

	<div class="form-group">
		<label class="form-label" for="departure-time">Vrijeme polaska</label>
		<input id="departure-time" class="form-input" type="time" bind:value={departureTime} />
	</div>

	<div class="form-group">
		<label class="form-label" for="exam-time">Vrijeme pregleda</label>
		<input id="exam-time" class="form-input" type="time" bind:value={examTime} />
	</div>

	<div class="form-group">
		<label class="form-label" for="return-time">Vrijeme povratka</label>
		<input id="return-time" class="form-input" type="time" bind:value={returnTime} />
	</div>

	<button type="button" class="btn-primary" onclick={closeSidePanel} style="margin-top: 8px;">
		Gotovo
	</button>
</div>

<!-- Confirmation dialog: Escape and backdrop never save; Escape = back to editing. -->
<dialog class="modal-card" bind:this={confirmDialog} aria-labelledby="confirm-title">
	<h2 class="modal-title" id="confirm-title">Provjerite unesene podatke</h2>
	<dl class="modal-summary">
		<dt>Ime i prezime</dt>
		<dd>{name.trim()}</dd>
		<dt>Mjesto stanovanja</dt>
		<dd>{location}</dd>
		<dt>Opis problema</dt>
		<dd>{description.trim()}</dd>
		<dt>Treba prijevoz</dt>
		<dd>{needsTransport ? 'Da' : 'Ne'}</dd>
		<dt>Nudi prijevoz drugima</dt>
		<dd>{willingToDrive ? 'Da' : 'Ne'}</dd>
		{#if departureTime}<dt>Vrijeme polaska</dt>
			<dd>{departureTime}</dd>{/if}
		{#if examTime}<dt>Vrijeme pregleda</dt>
			<dd>{examTime}</dd>{/if}
		{#if returnTime}<dt>Vrijeme povratka</dt>
			<dd>{returnTime}</dd>{/if}
	</dl>
	{#if !departureTime && !examTime && !returnTime}
		<p class="modal-note">Vremena nisu unesena. Termin i prijevoz još nisu planirani.</p>
	{/if}
	<div class="modal-actions">
		<button type="button" class="modal-btn modal-btn-green" onclick={confirmAndSave}>
			Potvrdi i spremi
		</button>
		<button type="button" class="modal-btn modal-btn-outline" onclick={backToEditing}>
			Ispravi podatke
		</button>
	</div>
</dialog>

<div class="page">
	<div class="page-header">
		<img src={logo} alt="OptiCare" class="logo-full" />
		<button class="back-link" onclick={goBack}>← Povratak</button>
	</div>

	<h1 class="page-title">Ispunite podatke o pacijentu</h1>

	<div class="time-indicator">
		<button type="button" class="time-open-btn" onclick={openSidePanel}>Ručni unos vremena</button>
		{#if examTime || departureTime || returnTime}
			{#if departureTime}<span>Polazak {departureTime}</span>{/if}
			{#if examTime}<span>Pregled {examTime}</span>{/if}
			{#if returnTime}<span>Povratak {returnTime}</span>{/if}
		{/if}
	</div>

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

		<button type="submit" class="btn-primary">Provjeri i spremi</button>
	</form>
</div>

<style>
	.intake-form {
		margin-top: 24px;
	}

	/* ─── Side panel ────────────────────── */
	.side-panel-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.3);
		z-index: 199;
		border: none;
		cursor: default;
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

	.time-open-btn {
		background: var(--green);
		color: white;
		border: none;
		padding: 8px 16px;
		border-radius: var(--radius-pill);
		font-weight: 600;
		font-size: 0.88rem;
		font-family: var(--font-sans);
		cursor: pointer;
	}

	.time-open-btn:hover {
		background: var(--green-dark);
	}

	.time-indicator span {
		background: white;
		border: 1px solid var(--border);
		border-radius: var(--radius-pill);
		padding: 3px 12px;
		font-weight: 600;
	}
</style>
