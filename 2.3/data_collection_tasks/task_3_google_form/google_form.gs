// google_form.gs
function createForm() {
  var form = FormApp.create('Форма збору даних');
  form.addTextItem().setTitle('Ім\'я').setRequired(true);
  form.addDateItem().setTitle('Дата').setRequired(true);
  form.addTextItem().setTitle('Відділ').setRequired(true);
  Logger.log('URL форми: ' + form.getPublishedUrl());
  Logger.log('ID форми: ' + form.getId());
}
